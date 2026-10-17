"""官方 SDK 的标准工具服务；四个入口与声明产生的 direct 共用同一运行时。"""
import base64
from functools import partial
import json

from layerweave import __version__
from .catalog import BASE_NAMES
from .runtime import Runtime, Outcome, REQUEST_ID


PAGE_LIMIT_DESCRIPTION = '本次结果的回复每页项数，不控制查询数量；命令有 limit 时填 arguments.limit。续取只传 cursor，沿用首次预算。'


def _schemas():
    query={'type':'object','properties':{
        'command':{'type':'string','description':'help 返回的完整命令身份'},
        'arguments':{'type':'object','description':'动作的 JSON 参数；先按需查 help'},
        'cursor':{'type':'string','description':'more.cursor：续取本次结果，不重做操作；业务 next_cursor 应放在原命令的翻页参数中'},
        'limit':{'type':'integer','minimum':1,'description':PAGE_LIMIT_DESCRIPTION},'max_chars':{'type':'integer','minimum':256,'description':'本次回复 JSON 字符预算；不改变命令查询范围'},
        'full':{'type':'boolean','default':False,'description':'完整返回本次已查到的结果，绕过回复分页预算；不扩大业务查询范围'}},'additionalProperties':False,
        'oneOf':[{'required':['command'],'not':{'required':['cursor']}},
                 {'required':['cursor'],'not':{'required':['command']}}]}
    write={**query,'properties':{k:v for k,v in query['properties'].items() if k!='cursor'},'required':['command']}
    write.pop('oneOf',None)
    help_schema={'type':'object','properties':{
        'topic':{'type':'string','enum':['commands','configs','skills','plugins','context'],'default':'commands'},
        'names':{'type':'array','items':{'type':'string'}},'search':{'type':'string'},'group':{'type':'string'},
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
        tools.append(types.Tool(name=name,description=descriptions[name],inputSchema=schemas[name],
            annotations=types.ToolAnnotations(readOnlyHint=name in ('layerweave_help','layerweave_query'),
                                               destructiveHint=name in ('layerweave_edit','layerweave_admin'),openWorldHint=True)))
    for name,binding in sorted(runtime.catalog.direct.items()):
        schema=runtime.schema(binding)
        schemas[name]=schema
        tools.append(types.Tool(name=name,description=binding.summary,inputSchema=schema,
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
            if name=='layerweave_query' and arguments.get('cursor'):
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
