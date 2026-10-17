"""通用调用适配；不重复业务事务、发号或检查规则。"""
from contextlib import closing
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, field
from difflib import get_close_matches
import importlib
import json
import logging
from pathlib import Path
import sqlite3
import sys
from urllib.parse import urlparse

from layerweave.support.feedback import InputError, error_detail, operation_result
from layerweave.support.api import open_database, change_cursor, read_record
from .catalog import Catalog, GROUPS
from .materials import read_skill
from .results import ResultPages, jsonable
from .settings import absolute, load_config


logger = logging.getLogger(__name__)
REQUEST_ID = ContextVar('layerweave_mcp_request_id',default=None)


@dataclass
class Outcome:
    data: dict
    is_error: bool = False
    images: list = field(default_factory=list)


class Runtime:
    def __init__(self, config=None):
        self.config = load_config(config)
        self.workspace = Path(self.config['workspace'])
        self.catalog = Catalog(self.config)
        self.pages = ResultPages(self.config['result_cache_size'])
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            return  # --list 的静态读取不要求安装可选运行依赖。
        for binding in self.catalog.bindings.values():
            try:
                Draft202012Validator.check_schema(binding.schema)
            except Exception as error:
                binding.enabled=False
                binding.reason='参数 Schema 不可用'
                self.catalog.issues.append({'code':'command_schema','id':binding.id,'message':str(error)})
                if binding.direct_name:
                    self.catalog.direct.pop(binding.direct_name,None)
                    binding.direct_name=None

    def context(self):
        return {key:self.config.get(key) for key in ('workspace','database','project_id')}

    def schema(self, binding):
        schema = deepcopy(binding.schema)
        required = schema.get('required',[])
        if self.config.get('database'):
            required = [x for x in required if x != 'database']
        if self.config.get('project_id') is not None and binding.options.get('default_project',True):
            required = [x for x in required if x != 'project_id']
        schema['required']=required
        return schema

    def help(self, topic='commands', *, names=None, search=None, group=None, audience='usage', **kwargs):
        if topic=='context':
            return {'context':self.context(),'issues':self.catalog.issues}
        if topic=='configs':
            binding = self.catalog.resolve('layerweave.config_help')
            arguments = {**kwargs,'audience':audience}
            if names is not None:
                arguments['targets']=names
            return self.invoke('query',binding.id,arguments).data
        if topic=='plugins':
            binding = self.catalog.resolve('layerweave.view_plugin')
            if names:
                return {'items':[self.invoke('query',binding.id,{'action':'info','target':name,**kwargs}).data for name in names]}
            return self.invoke('query',binding.id,{'action':'list',**kwargs}).data
        if topic not in ('commands','skills'):
            raise InputError('未知帮助话题',field='topic',allowed=['commands','configs','skills','plugins','context'])
        if names is not None:
            requested = [names] if isinstance(names,str) else names
            items,issues = [],[]
            for name in requested:
                try:
                    if topic=='commands':
                        documented=[c for c in self.catalog.documentation if name in {c['id'],c['name'],*c.get('aliases',[])}]
                        if len(documented)==1 and name not in self.catalog.bindings:
                            c=documented[0]
                            items.append({'id':c['id'],'summary':c['summary'],'availability':'documentation_only',
                                'reason':c['reason'],'input_schema':c['input_schema'],'cli':c.get('cli'),
                                'returns':c.get('returns',''),'examples':c.get('examples',[])})
                            continue
                    binding = self.catalog.resolve(name,allow_disabled=True)
                    if topic=='skills':
                        if binding.material is None:
                            raise InputError('目标不是技能材料',id=binding.id)
                        if not binding.enabled:
                            raise InputError('技能已禁用',id=binding.id)
                        items.append(read_skill(binding.material,resource=kwargs.get('resource')))
                    else:
                        item = {**self.catalog.summary(binding),'input_schema':self.schema(binding),
                                'returns':binding.options.get('returns',binding.command.get('returns','见 result；操作与检查分别报告')),
                                'notes':binding.options.get('notes',binding.command.get('notes',[])),
                                'examples':self.examples(binding),'example_note':'示例编号、路径及素材替换为实际目标；数据可直接传入，无需创建文件。'}
                        if audience=='developer':
                            item.update({k:binding.command.get(k) for k in ('source','source_root','entrypoint','session_entrypoint','cli')})
                            item['binding']=deepcopy(binding.options)
                            item['cli_mapping']=binding.command.get('cli_mapping',{})
                        items.append(item)
                except (InputError,OSError,ValueError) as error:
                    issues.append({'target':name,**error_detail(error)})
            return {'view':'details','status':'partial' if issues else 'completed','items':items,'issues':issues}
        bindings = [b for b in self.catalog.bindings.values() if (topic!='skills' or b.material)]
        if group:
            bindings=[b for b in bindings if b.group==group]
        if search:
            phrase=search.casefold()
            bindings=[b for b in bindings if phrase in ' '.join((b.id,b.summary,*b.command.get('aliases',[]))).casefold()]
        if group or search or topic=='skills':
            return {'view':'matches','items':[self.catalog.summary(b) for b in bindings], 'issues':self.catalog.issues}
        groups=[]
        for name in sorted({b.group for b in bindings}):
            active=[b for b in bindings if b.group==name and b.enabled]
            groups.append({'group':name,'summary':GROUPS.get(name,name),'count':len(active),
                           'common':[self.catalog.summary(b) for b in active[:3]]})
        return {'view':'overview','groups':groups,'documentation_only':[
                    {'id':c['id'],'summary':c['summary'],'reason':c['reason'],'cli':c.get('cli')} for c in self.catalog.documentation],
                'next':'指定 group/search 查目录，指定 names 展开参数和示例；已知用法可直接调用。',
                'issues':self.catalog.issues}

    def examples(self,binding):
        arguments={}
        for name,spec in binding.schema.get('properties',{}).items():
            if name not in binding.schema.get('required',[]):
                continue
            if 'examples' in spec:
                value=spec['examples'][0]
            elif 'default' in spec:
                value=spec['default']
            elif name=='database':
                value=self.config.get('database') or str(self.workspace/'project.sqlite3')
            elif name=='project_id':
                value=self.config.get('project_id') or 1
            elif spec.get('enum'):
                value=spec['enum'][0]
            else:
                kind=spec.get('type','object')
                kind=kind[0] if isinstance(kind,list) else kind
                value={'integer':1,'number':1,'string':'填写实际值','array':[],'object':{},'boolean':False}.get(kind)
            arguments[name]=value
        for example in binding.command.get('examples',[]):
            if example.get('arguments'):
                arguments.update(deepcopy(example['arguments']))
                break
        arguments={k:v for k,v in arguments.items() if k in binding.schema.get('properties',{})}
        route=binding.route(arguments)
        examples=[{'tool':'layerweave_'+route,'arguments':{'command':binding.id,'arguments':arguments}}]
        if binding.direct_name:
            examples.append({'tool':binding.direct_name,'arguments':arguments})
        return examples

    def _arguments(self,binding,arguments):
        if not isinstance(arguments,dict):
            raise InputError('arguments 必须为 JSON 对象',field='arguments')
        values=deepcopy(arguments)
        props=binding.schema.get('properties',{})
        explicit_db=values.get('database')
        if 'database' in props and 'database' not in values and self.config.get('database'):
            values['database']=self.config['database']
        same_db=explicit_db is None or absolute(explicit_db,self.workspace)==self.config.get('database')
        if ('project_id' in binding.command.get('context',[]) and 'project_id' not in values and same_db
                and binding.options.get('default_project',True) and self.config.get('project_id') is not None):
            values['project_id']=self.config['project_id']
        # 调用默认值只填顶层，不递归改写 information 或交换文档。
        for name,spec in props.items():
            if name not in values and 'default' in spec:
                values[name]=deepcopy(spec['default'])
        from jsonschema import Draft202012Validator
        errors=sorted(Draft202012Validator(binding.schema).iter_errors(values),key=lambda e:list(map(str,e.path)))
        if errors:
            error=errors[0]
            location='.'.join(map(str,error.path)) or 'arguments'
            detail={'field':location,'rule':error.validator}
            if error.validator=='additionalProperties':
                unknown=set(values)-set(props)
                detail.update(allowed=list(props),suggestions={key:get_close_matches(key,props,n=1) for key in unknown})
            if error.validator=='required':
                detail['missing']=[key for key in error.validator_value if key not in error.instance]
            if error.validator=='enum':
                detail['allowed']=error.validator_value
            raise InputError('调用参数不符合声明，请按字段和规则修正；业务内容仍由原有检查处理。',**detail)
        path_names=set(binding.options.get('paths',[])) | ({'database'} if 'database' in props else set())
        path_names.update(binding.options.get('action_paths',{}).get(values.get('action'),[]))
        for name in path_names:
            if values.get(name) is not None:
                values[name]=absolute(values[name],self.workspace)
        for name in binding.options.get('uri_paths',[]):
            if values.get(name) and urlparse(values[name]).scheme not in ('http','https'):
                values[name]=absolute(values[name],self.workspace)
        for name in binding.options.get('path_arrays',[]):
            if values.get(name) is not None:
                values[name]=[absolute(p,self.workspace) for p in values[name]]
        return values

    def _function(self,binding):
        entry=binding.options.get('handler') or binding.command.get('entrypoint')
        if not entry:
            raise InputError('该条目没有可调用入口',command=binding.id)
        root=binding.command.get('import_root')
        if root and root not in sys.path:
            sys.path.insert(0,root)
        module,attr=entry.split(':',1)
        function=importlib.import_module(module)
        for part in attr.split('.'):
            function=getattr(function,part)
        return function

    def _call(self,binding,values,route):
        if binding.material:
            return read_skill(binding.material,**values),None
        function=self._function(binding)
        mode=binding.options.get('database')
        path=values.get('database')
        if mode and (not path or not Path(path).is_file()):
            raise InputError('数据库不存在，请先用 initialize_database 初始化',field='database')
        if mode=='connection':
            if route=='query':
                connection=sqlite3.connect(Path(path).as_uri()+'?mode=ro',uri=True)
                connection.row_factory=sqlite3.Row
                connection.execute('PRAGMA foreign_keys=ON')
                connection.execute('PRAGMA query_only=ON')
            else:
                connection=open_database(path)
            with closing(connection):
                before=change_cursor(connection) if route=='query' else None
                result=function(connection,**{k:v for k,v in values.items() if k!='database'})
                after=change_cursor(connection) if route=='query' else None
            if before is not None and before!=after:
                raise InputError('读取期间业务数据发生变化，请重新查询；本次没有执行写入。',code='read_changed')
            return result, {'database':path,'cursor':after} if after is not None else None
        result=function(**values)
        return result,None

    def invoke(self,route,command,arguments=None,*,limit=None,max_chars=None,full=False):
        context={}
        result=None
        executed=False
        try:
            for key,value,minimum in (('limit',limit,1),('max_chars',max_chars,256)):
                if value is not None and (type(value) is not int or value<minimum):
                    raise InputError(f'{key} 需要不小于 {minimum} 的整数',field=key)
            binding=self.catalog.resolve(command)
            values=self._arguments(binding,{} if arguments is None else arguments)
            actual=binding.route(values)
            if route!=actual:
                raise InputError('该动作不能通过此入口执行',command=binding.id,required_tool='layerweave_'+actual)
            context={k:values[k] for k in ('database','project_id') if k in values}
            result,version=self._call(binding,values,route)
            executed=True
            images=[]
            # 媒体适配器返回字节，与业务 JSON 分开；SDK 只在最外层编码。
            if binding.options.get('output')=='image' and isinstance(result,dict):
                result=dict(result)
                if '_image' in result:
                    images.append(result.pop('_image'))
            result=jsonable(result)
            if (binding.options.get('journal_result') and isinstance(result,dict)
                    and result.get('operation_id') and 'operation' not in result):
                # 旧视图入口只返回编号；从已提交日志补充反馈，不重复写入或发放编号。
                with closing(sqlite3.connect(Path(values['database']).as_uri()+'?mode=ro',uri=True)) as read:
                    read.row_factory=sqlite3.Row
                    changes=read_record(read,'change',filters={'operation_id':result['operation_id']})
                result={**result,'operation':operation_result('committed' if changes else 'unchanged',
                    [{'action':c['action'],'kind':c['kind'],'project_id':c['project_id'],'id':c['target_id']} for c in changes])}
            if isinstance(result,dict):
                rows=result.get('results',[result])
                scopes={r.get('project_id') for r in rows if isinstance(r,dict) and r.get('project_id') is not None}
                for row in rows:
                    if isinstance(row,dict) and row.get('kind')=='project' and isinstance(row.get('data'),dict):
                        if row['data'].get('id') is not None:
                            scopes.add(row['data']['id'])
                for change in result.get('operation',{}).get('changes',[]):
                    target=change.get('target',{})
                    identity=target.get('id') if target.get('kind')=='project' else target.get('project_id')
                    if identity is not None:
                        scopes.add(identity)
                if result.get('project_id') is not None:
                    scopes.add(result['project_id'])
                data=result.get('data')
                if isinstance(data,dict) and data.get('project_id') is not None:
                    scopes.add(data['project_id'])
                if scopes:
                    context.update({'project_id':next(iter(scopes))} if len(scopes)==1 else {'project_ids':sorted(scopes)})
                    if len(scopes)>1:
                        context.pop('project_id',None)
            envelope={'context':context,'result':result}
            operation=result.get('operation',{}) if isinstance(result,dict) else {}
            if isinstance(result,dict) and result.get('operation_id'):
                logger.info('request=%s command=%s operation_id=%s status=%s',REQUEST_ID.get(),binding.id,result['operation_id'],operation.get('status'))
                if operation.get('status')=='committed' and operation.get('changes'):
                    envelope['undo']={'tool':'layerweave_edit','arguments':{'command':'layerweave.undo_operation',
                                      'arguments':{'database':values.get('database'),'operation_id':result['operation_id']}}}
            failed=isinstance(result,dict) and (result.get('ok') is False or operation.get('status')=='failed')
            envelope=self.pages.first(envelope,limit=limit or self.config['limit'],max_chars=max_chars or self.config['max_chars'],
                                      full=full,document=binding.options.get('output')=='document',version=version)
            return Outcome(envelope,failed,images)
        except Exception as error:
            logger.info('request=%s command=%s failed=%s',REQUEST_ID.get(),command,type(error).__name__)
            data={'context':context,'error':error_detail(error),
                  'note':'未拿到写入响应时先核对历史和目标，不要自动重做。'}
            if executed and isinstance(result,dict):
                data['operation_id']=result.get('operation_id')
                data['operation']=result.get('operation')
                data['checks']=result.get('checks')
                if result.get('operation',{}).get('status')=='committed':
                    data['note']='业务写入已经提交，但返回整理失败。请按 operation_id 查历史，不要重做。'
            return Outcome(data,True)

    def continue_result(self,cursor):
        try:
            version=self.pages.version(cursor)
            if version:
                with closing(sqlite3.connect(Path(version['database']).as_uri()+'?mode=ro',uri=True)) as connection:
                    if change_cursor(connection)!=version['cursor']:
                        raise InputError('分页后业务数据已变化，请重新查询；没有重做原操作。',code='cursor_stale')
            data=self.pages.page(cursor)
            raw=data.get('result')
            failed=data.get('execution_failed',False) or (isinstance(raw,dict) and raw.get('ok') is False)
            return Outcome(data,failed)
        except Exception as error:
            return Outcome({'error':error_detail(error)},True)
