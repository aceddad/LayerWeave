"""视图的 JSON/媒体适配。由视图自己的 COMMANDS 绑定，MCP 宿主不认识视图特例。"""
import json
from pathlib import Path
import tempfile


def _params(values):
    if values is None:
        return None
    return [key+'='+(value if isinstance(value,str) else json.dumps(value,ensure_ascii=False,allow_nan=False))
            for key,value in values.items()]


def _capture(database,project_id,**arguments):
    from .screenshot import capture
    arguments['params']=_params(arguments.get('params'))
    with tempfile.TemporaryDirectory(prefix='layerweave-mcp-image-') as folder:
        output=Path(folder)/'capture.png'
        result=capture(database,project_id,output,**arguments)
        result.pop('output',None)
        result.pop('page',None)  # 截图后本地临时服务已经关闭。
        return result,output.read_bytes()


def look(database,project_id,**arguments):
    result,image=_capture(database,project_id,**arguments)
    return {**result,'saved':False,'_image':image}


def _save_new(output,data):
    path=Path(output).resolve()
    path.parent.mkdir(parents=True,exist_ok=True)
    # 排他创建由写入本身保证；不能先 exists 再覆盖。
    with path.open('xb') as stream:
        stream.write(data)
    return str(path)


def save_screenshot(database,project_id,output,**arguments):
    result,image=_capture(database,project_id,**arguments)
    return {**result,'saved':True,'output':_save_new(output,image)}


def save_frame(database,project_id,object_id,output,**arguments):
    from .frame import grab
    with tempfile.TemporaryDirectory(prefix='layerweave-mcp-frame-') as folder:
        path=Path(folder)/'frame.png'
        result=grab(database,project_id,object_id,path,**arguments)
        data=path.read_bytes()
    return {**result,'output':_save_new(output,data)}


def inbox(database,project_id,*,status='open',waiting=None):
    from .note import note
    return note(database,project_id,'list',status=status,waiting=waiting)


def note_action(database,project_id,action='list',**arguments):
    from layerweave.support.feedback import InputError
    from .note import note
    if action in ('add','reply'):
        author=arguments.get('author')
        if not isinstance(author,str) or not author.strip():
            raise InputError('MCP 写批注需要非空 author；请与 waiting 使用同一署名标签。',
                             code='invalid_author',field='author',phase='parameters')
    return note(database,project_id,action,**arguments)


def reply(database,project_id,note_id,text,*,author=None):
    return note_action(database,project_id,'reply',note_id=note_id,text=text,author=author)
