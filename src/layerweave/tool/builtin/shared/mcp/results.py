"""有界回复与同次结果续取；不会为翻页重新执行写操作。"""
from collections import OrderedDict
from copy import deepcopy
import json
from threading import RLock
from uuid import uuid4

from layerweave.support.feedback import InputError


def jsonable(value):
    from pathlib import Path
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k):jsonable(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)):
        return [jsonable(v) for v in value]
    return value


def encoded(value):
    return json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':'))


_MISSING = object()


def _value(value, path):
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return _MISSING
        value = value[key]
    return value


def _primary_list(value, declared=None):
    if declared is not None:
        found = _value(value, declared)
        return (tuple(declared), found) if isinstance(found, list) else ((), None)
    # 只选唯一的最外层列表，不进入列表项，也不凭长度猜业务主次。
    level = [((), value)]
    while level:
        lists = [(path, node) for path, node in level if isinstance(node, list)]
        if lists:
            return lists[0] if len(lists) == 1 else ((), None)
        level = [(path + (key,), child) for path, node in level if isinstance(node, dict)
                 for key, child in node.items() if isinstance(child, (dict, list))]
    return (), None


def _replace(value, path, replacement):
    if not path:
        return replacement
    result = deepcopy(value)
    node = result
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = replacement
    return result


class ResultPages:
    def __init__(self, size=32):
        self.size = size
        self.records = OrderedDict()
        self.lock = RLock()

    def _remember(self,key,record):
        with self.lock:
            self.records[key]=record
            while len(self.records)>self.size:
                self.records.popitem(last=False)

    def first(self, envelope, *, limit, max_chars, full=False, document=False, version=None, pagination=None):
        text = encoded(envelope)
        # 交换文档不按项目数量拆分；外层 limit 不解释为导出范围。
        if full:
            return {**envelope,'result_complete':True}
        if document:
            if len(text) <= max_chars:
                return {**envelope,'result_complete':True}
            raise InputError('交换文档超出当前返回预算，未截断、未保存文件。缩小范围或明确 full=true；也可选择文件导出。',
                             code='result_too_large',characters=len(text),limit=max_chars)
        pagination = pagination or {}
        primary_path, values = _primary_list(envelope.get('result'), pagination.get('items'))
        if len(text)<=max_chars and (values is None or len(values)<=limit):
            return {**envelope,'result_complete':True}
        key = uuid4().hex
        # 保留一条业务项的内部结构；一项过大则明确按 JSON 文本分段。
        mode, path = 'json_chunks', ()
        if values:
            skeleton = _replace(envelope['result'],primary_path,[])
            if len(encoded({**envelope,'result':skeleton}))+256 < max_chars:
                mode,path = 'items',primary_path
        next_path = pagination.get('next_cursor')
        if next_path is not None and _value(envelope.get('result'), next_path) is _MISSING:
            next_path = None
        record = {'envelope':deepcopy(envelope),'text':text,'mode':mode,'path':path,
                  'limit':limit,'max_chars':max_chars,'version':version,'next_path':next_path}
        self._remember(key,record)
        return self.page(key+':0')

    def version(self, cursor):
        key = str(cursor).partition(':')[0]
        with self.lock:
            record = self.records.get(key)
        if record is None:
            raise InputError('续取结果已失效。查询可重查；写入结果请先查历史，不要重做写入。',code='cursor_expired')
        return record['version']

    def page(self, cursor):
        parts=str(cursor).split(':')
        if len(parts) not in (2,4) or not parts[-1].isdecimal():
            raise InputError('无效的结果游标',code='invalid_cursor')
        key,start=parts[0],int(parts[-1])
        with self.lock:
            record = self.records.get(key)
        if record is None:
            raise InputError('结果缓存已失效；写入请查历史，不要重复执行。',code='cursor_expired')
        if len(parts)==4:
            fragment=record.get('fragments',{}).get(parts[2]) if parts[1]=='fragment' else None
            if fragment is None:
                raise InputError('片段游标已失效',code='invalid_cursor')
            return self._fragment(record,fragment['text'],str(cursor),start,fragment['after'],fragment['path'])
        original = record['envelope']
        if record['mode']=='items':
            values = original['result']
            for segment in record['path']:
                values = values[segment]
            if start > len(values):
                raise InputError('游标位置超出结果',code='invalid_cursor')
            end = min(len(values),start+record['limit'])
            result = {**deepcopy(original),'result':_replace(original['result'],record['path'],values[start:end]),'result_complete':False}
            while end>start and len(encoded(result))+256>record['max_chars']:
                end-=1
                result['result']=_replace(original['result'],record['path'],values[start:end])
            if end==start and start<len(values):
                # 单个对象很大时给出可前进的文本分段，不能永远返回空页。
                fragment = encoded(values[start])
                fragment_key = uuid4().hex
                # 片段仍属于原快照，不新占一个缓存槽，也不会挤掉待续取的父结果。
                with self.lock:
                    record.setdefault('fragments',{})[fragment_key]={'text':fragment,
                        'after':key+':'+str(start+1),'path':list(record['path'])+[start]}
                return self._fragment(record,fragment,key+':fragment:'+fragment_key+':0',0,
                                      key+':'+str(start+1),list(record['path'])+[start])
            remaining = len(values)-end
            if remaining and record['next_path'] is not None:
                result['result'] = _replace(result['result'], record['next_path'], None)
            result['more']={'remaining':remaining,'unit':'items','has_more':bool(remaining),'path':list(record['path']),
                            'cursor':key+':'+str(end) if remaining else None,
                            'how':'先用 layerweave_query 的 cursor 续取本次结果；读完后再用业务游标查询下一批。result 为局部页，不能整体写回。'}
            self._business_cursor(result, record, bool(remaining))
            return result
        text = record['text']
        return self._fragment(record,text,key+':'+str(start),start,record.get('after'),record.get('fragment_of',[]))

    def _fragment(self,record,text,cursor,start,after,path):
        original=record['envelope']
        if start>len(text):
            raise InputError('游标位置超出结果',code='invalid_cursor')
        end = min(len(text),start+max(64,record['max_chars']-768))
        result={'context':deepcopy(original.get('context',{})),'result':None,'result_complete':False,
                'fragment':{'format':'json_text','offset':start,'text':text[start:end],
                            'total_characters':len(text),'path':path},
                'more':{'remaining':len(text)-end,'unit':'characters','has_more':end<len(text) or after is not None,
                        'cursor':cursor.rsplit(':',1)[0]+':'+str(end) if end<len(text) else after,
                        'how':'这是 JSON 文本片段，需按 offset 拼接；不要将片段直接导入。'}}
        self._business_cursor(result, record, result['more']['has_more'])
        raw=original.get('result')
        if isinstance(raw,dict) and raw.get('operation_id'):
            result['operation_id']=raw['operation_id']
            result['operation']={k:v for k,v in raw.get('operation',{}).items() if k!='changes'}
            result['operation']['change_count']=len(raw.get('operation',{}).get('changes',[]))
        if isinstance(raw,dict) and raw.get('ok') is False:
            result['execution_failed']=True
        if original.get('undo'):
            result['undo']=deepcopy(original['undo'])
        return result

    @staticmethod
    def _business_cursor(result, record, pending):
        if record['next_path'] is not None:
            result['more'].update(business_cursor_path=list(record['next_path']), business_cursor_pending=pending)
