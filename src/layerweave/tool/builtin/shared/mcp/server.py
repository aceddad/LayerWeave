"""官方 SDK 的标准工具服务；四个入口与声明产生的 direct 共用同一运行时。"""
import base64
from copy import deepcopy
from functools import partial
import json

from layerweave import __version__
from .catalog import BASE_NAMES
from .runtime import Runtime, Outcome, REQUEST_ID


PAGE_LIMIT_DESCRIPTION = '本次结果的回复每页项数，不控制查询数量；命令有 limit 时填 arguments.limit。续取只传 cursor，沿用首次预算。'
ROOT_COMBINATORS = frozenset(('oneOf', 'anyOf', 'allOf', 'not', 'if', 'then', 'else'))


def _advertised_schema(schema):
    """客户端兼容说明；只省略根级组合/条件，嵌套定义和服务端完整规则保持。"""
    return {key:deepcopy(value) for key,value in schema.items() if key not in ROOT_COMBINATORS}


def _schemas():
    query={'type':'object','properties':{
        'command':{'type':'string','minLength':1,'pattern':r'\S','description':'发起查询时填写 help 返回的命令身份；与 cursor 二选一，不能同时提供'},
        'arguments':{'type':'object','description':'动作的 JSON 参数；先按需查 help'},
        'cursor':{'type':'string','minLength':1,'pattern':r'\S','description':'续页时只填 more.cursor，与 command 二选一；不重做操作，沿用首次预算。业务 next_cursor 放在原命令参数中'},
        'limit':{'type':'integer','minimum':1,'description':PAGE_LIMIT_DESCRIPTION},'max_chars':{'type':'integer','minimum':256,'description':'本次回复 JSON 字符预算；不改变命令查询范围'},
        'full':{'type':'boolean','default':False,'description':'完整返回本次已查到的结果，绕过回复分页预算；不扩大业务查询范围'}},'additionalProperties':False,
        'oneOf':[{'required':['command'],'not':{'required':['cursor']}},
                 {'required':['cursor'],'not':{'required':['command']}}]}
    write={**query,'properties':{k:v for k,v in query['properties'].items() if k!='cursor'},'required':['command']}
    write.pop('oneOf',None)
    write['properties']['command']={'type':'string','minLength':1,'pattern':r'\S','description':'help 返回的完整命令身份'}
    help_schema={'type':'object','properties':{
        'topic':{'type':'string','enum':['commands','configs','skills','plugins','context'],'default':'commands'},
        'names':{'type':'array','items':{'type':'string'}},'search':{'type':'string','description':'按空白分词，任一词命中即可；完整短语优先，其次按命中词数排序'},'group':{'type':'string'},
        'audience':{'enum':['usage','developer'],'default':'usage'},
        'view':{'enum':['overview','layers','objects','combined']},'config_root':{'type':'string'},
        'resource':{'type':'string'},'root':{'type':'string'},
        'limit':{'type':'integer','minimum':1,'description':PAGE_LIMIT_DESCRIPTION},'max_chars':{'type':'integer','minimum':256,'description':'本次回复 JSON 字符预算；不改变命令查询范围'},'full':{'type':'boolean','description':'完整返回本次帮助，绕过回复分页预算'}},
        'additionalProperties':False}
    return {'layerweave_help':help_schema,'layerweave_query':query,'layerweave_edit':write,'layerweave_admin':write}


def create_server(config=None):
    import anyio
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import best_match
    from mcp.server.lowlevel import Server
    from mcp.shared.exceptions import MCPError
    from mcp import types
    from layerweave.support.feedback import error_detail
    runtime=config if isinstance(config,Runtime) else Runtime(config)
    schemas=_schemas()
    descriptions={
        'layerweave_help':'查 LayerWeave 能力：分类、关键词、多个命令详情、层/对象配置、技能说明、插件和默认上下文。不需要数据库。',
        'layerweave_query':'查询项目、导出 JSON、读取材料或看图。传 command 与 arguments；参数按需查 help。外层 limit 是回复页大小；查询几条用 arguments.limit。more.cursor 读完本次结果后，再用业务游标查下一批。',
        'layerweave_edit':'修改项目、直接传入 JSON、批量 CRUD 或撤销。写入结果与 checks 分开；没有响应时先查历史，不自动重做。',
        'layerweave_admin':'初始化库、安装、修改配置或明确保存文件。具体动作按需查 help；展示此入口不等于已获客户端授权。'}
    tools=[]
    for name in sorted(BASE_NAMES):
        tools.append(types.Tool(name=name,description=descriptions[name],inputSchema=_advertised_schema(schemas[name]),
            annotations=types.ToolAnnotations(readOnlyHint=name in ('layerweave_help','layerweave_query'),
                                               destructiveHint=name in ('layerweave_edit','layerweave_admin'),openWorldHint=True)))
    for name,binding in sorted(runtime.catalog.direct.items()):
        schema=runtime.schema(binding)
        schemas[name]=schema
        tools.append(types.Tool(name=name,description=binding.summary,inputSchema=_advertised_schema(schema),
            annotations=types.ToolAnnotations(readOnlyHint=binding.routes()==['query'],
                                               destructiveHint=binding.routes()!=['query'],openWorldHint=binding.options.get('open_world',True))))

    async def list_tools(context,params):
        return types.ListToolsResult(tools=tools,ttlMs=0,cacheScope='private')

    def call(name,arguments):
        if name=='layerweave_help':
            args=dict(arguments)
            page={key:args.pop(key) for key in ('limit','max_chars','full') if key in args}
            try:
                data=runtime.help(**args)
                page_path = 'groups' if data.get('view')=='overview' else 'items'
                pagination = {'items':[page_path]} if isinstance(data.get(page_path),list) else None
                envelope={'context':runtime.context(),'result':data}
                return Outcome(runtime.pages.first(envelope,limit=page.get('limit',runtime.config['limit']),
                    max_chars=page.get('max_chars',runtime.config['max_chars']),full=page.get('full',False),pagination=pagination))
            except Exception as error:
                return Outcome({'error':error_detail(error)},True)
        if name in BASE_NAMES:
            if name=='layerweave_query' and 'cursor' in arguments:
                return runtime.continue_result(arguments['cursor'])
            return runtime.invoke(name.removeprefix('layerweave_'),arguments['command'],arguments.get('arguments'),
                **{k:arguments[k] for k in ('limit','max_chars','full') if k in arguments})
        binding=runtime.catalog.direct[name]
        # 路由判定与执行都走同一校验/默认值处理，独立入口不提供第二套行为。
        try:
            args=runtime._arguments(binding,arguments)
            return runtime.invoke(binding.route(args),binding.id,arguments)
        except Exception as error:
            return Outcome({'error':error_detail(error)},True)

    async def call_tool(context,params):
        if params.name not in schemas:
            raise MCPError(code=-32602,message='未知 MCP 工具；请重新读取工具列表。')
        error=best_match(Draft202012Validator(schemas[params.name]).iter_errors(params.arguments or {}))
        if error is not None:
            detail={'code':'request_schema','field':'.'.join(map(str,error.absolute_path)) or 'arguments',
                    'rule':error.validator,'message':'请求不符合该入口的参数结构，请按 field 和 rule 修正。'}
            if params.name=='layerweave_query' and error.validator=='oneOf' and not error.absolute_path:
                detail.update(fields=['command','cursor'],message=(
                    'command 与 cursor 不能同时提供：新查询传 command，续页只传 cursor。'
                    if 'command' in (params.arguments or {}) and 'cursor' in (params.arguments or {})
                    else '请提供 command 或 cursor：新查询传 command，续页只传 cursor。'))
            if params.name in BASE_NAMES and error.validator in ('minLength','pattern') and detail['field'] in ('command','cursor'):
                detail['message']=f"{detail['field']} 不能为空或只含空白。"
            if error.validator=='required':
                detail['missing']=[key for key in error.validator_value if key not in error.instance]
            if error.validator=='additionalProperties':
                detail['allowed']=list(error.schema.get('properties',{}))
            data={'error':detail}
            return types.CallToolResult(content=[types.TextContent(type='text',text=json.dumps(data,ensure_ascii=False))],
                                        structuredContent=data,isError=True)
        # SDK 校验协议参数；工作线程不因客户端放弃等待就自动重复/撤销已运行的写入。
        token=REQUEST_ID.set(context.request_id)
        try:
            outcome=await anyio.to_thread.run_sync(partial(call,params.name,params.arguments or {}),abandon_on_cancel=False)
        finally:
            REQUEST_ID.reset(token)
        content=[types.TextContent(type='text',text=json.dumps(outcome.data,ensure_ascii=False,allow_nan=False))]
        content.extend(types.ImageContent(type='image',data=base64.b64encode(blob).decode('ascii'),mimeType='image/png') for blob in outcome.images)
        return types.CallToolResult(content=content,structuredContent=outcome.data,isError=outcome.is_error)

    return Server('layerweave',version=__version__,
        instructions='LayerWeave：未知能力先查 layerweave_help，熟悉后可直接调用。JSON 可直接读写，文件和视图均非前置步骤。操作是否提交看 result.operation，checks 不代表写入失败。',
        get_tool_input_schema=schemas.get,on_list_tools=list_tools,on_call_tool=call_tool)
