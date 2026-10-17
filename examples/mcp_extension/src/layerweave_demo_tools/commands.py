"""声明发现不执行本模块；调用时才装载普通函数。"""


def summarize_text(text):
    return {'characters':len(text),'lines':len(text.splitlines()),'preview':text[:80]}


COMMANDS = [{
    'name':'summarize_text',
    'summary':'统计传入文本的字符和行数；只返回摘要，不修改项目',
    'entrypoint':'layerweave_demo_tools.commands:summarize_text',
    'read_only':True,
    'input_schema':{'type':'object','properties':{'text':{'type':'string','description':'待统计的文本'}},
                    'required':['text'],'additionalProperties':False},
    'returns':'characters、lines 与最多80字符的 preview',
    'examples':[{'arguments':{'text':'第一行\n第二行'}}],
    'mcp':{'route':'query','group':'text','exposure':'direct'},
}]
