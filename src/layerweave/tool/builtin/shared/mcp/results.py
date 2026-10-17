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


def _lists(value, path=()):
    if isinstance(value,list):
        yield path,value
        for i, child in enumerate(value):
            yield from _lists(child,(*path,i))
    elif isinstance(value,dict):
        for key,child in value.items():
            yield from _lists(child,(*path,key))


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

    def first(self, envelope, *, limit, max_chars, full=False, document=False, version=None):
        text = encoded(envelope)
        candidates = list(_lists(envelope.get('result')))
        longest = max(candidates,key=lambda row:len(row[1]),default=((),[]))
        if full or (len(text)<=max_chars and len(longest[1])<=limit):
            return {**envelope,'result_complete':True}
        if document:
            raise InputError('交换文档超出当前返回预算，未截断、未保存文件。缩小范围或明确 full=true；也可选择文件导出。',
                             code='result_too_large',characters=len(text),limit=max_chars)
        key = uuid4().hex
        # 先尝试按原结果中的列表分页，保留树层级及其他上下文；无法容纳一项时按完整 JSON 文本分段。
        mode, path = 'json_chunks', ()
        if longest[1]:
            skeleton = _replace(envelope['result'],longest[0],[])
            if len(encoded({**envelope,'result':skeleton}))+256 < max_chars:
                mode,path = 'items',longest[0]
        record = {'envelope':deepcopy(envelope),'text':text,'mode':mode,'path':path,
                  'limit':limit,'max_chars':max_chars,'version':version}
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
            result['more']={'remaining':remaining,'unit':'items','has_more':bool(remaining),'path':list(record['path']),
                            'cursor':key+':'+str(end) if remaining else None,
                            'how':'用 layerweave_query 的 cursor 继续；result 为局部页，不能当作完整对象整体写回。'}
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
