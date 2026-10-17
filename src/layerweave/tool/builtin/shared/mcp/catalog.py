"""启动时的统一绑定目录；工具来源与 direct/routed 使用相同规则。"""
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from difflib import get_close_matches
import re

from layerweave.support.commands import discover_commands
from layerweave.support.command_schema import select_parameters
from layerweave.support.feedback import InputError
from .materials import discover_skills


BASE_NAMES = {'layerweave_help','layerweave_query','layerweave_edit','layerweave_admin'}
GROUPS = {'query':'查看项目','records':'记录读写','editing':'编辑与时间位置','exchange':'JSON 交换',
          'history':'历史','undo':'撤销','validation':'复查','text':'文本',
          'developer':'开发管理','view':'视图','help':'帮助','skills':'技能材料'}


@dataclass
class Binding:
    id: str
    command: dict
    schema: dict
    options: dict
    material: dict | None = None
    enabled: bool = True
    reason: str | None = None
    direct_name: str | None = None

    @property
    def group(self):
        return self.options.get('group', 'other')

    @property
    def summary(self):
        return self.options.get('summary', self.command.get('summary', self.id))

    def route(self, arguments):
        selector = self.options.get('route_by')
        if selector == 'request':
            requests = arguments.get('request', [])
            requests = requests if isinstance(requests, list) else [requests]
            return 'query' if all(isinstance(r,dict) and r.get('action') == 'read' for r in requests) else 'edit'
        if selector == 'upgrade':
            return 'admin' if arguments.get('upgrade',False) else 'query'
        if selector == 'action':
            action = arguments.get('action', self.schema.get('properties',{}).get('action',{}).get('default'))
            route = self.options.get('action_routes',{}).get(action)
            if route is None:
                raise InputError('未知 action',field='action',allowed=list(self.options.get('action_routes',{})))
            if arguments.get('output') and self.options.get('output_path_route'):
                return self.options['output_path_route']
            return route
        return self.options.get('route', 'admin')

    def routes(self):
        if self.options.get('route_by') == 'request':
            return ['query','edit']
        if self.options.get('route_by') == 'upgrade':
            return ['query','admin']
        values = self.options.get('action_routes')
        if values:
            return sorted(set(values.values()) | ({self.options['output_path_route']} if self.options.get('output_path_route') else set()))
        return [self.options.get('route','admin')]


class Catalog:
    def __init__(self, config):
        self.config = config
        commands, self.issues = discover_commands(sources=config['sources'],
            include_builtin=config['include_builtin'], installed=config['installed'])
        candidates = []
        self.documentation = []
        for command in commands:
            declaration = command.get('mcp')
            if declaration is not None and not isinstance(declaration,dict):
                self.issues.append({'code':'mcp_declaration','id':command['id'],'message':'mcp 声明需要对象'})
                continue
            if not declaration or declaration.get('enabled') is False:
                self.documentation.append({**command,'availability':'documentation_only',
                    'reason':(declaration or {}).get('reason','尚未提供 MCP 调用适配')})
                continue
            base = {k:v for k,v in declaration.items() if k != 'variants'}
            variants=declaration.get('variants',[])
            if not isinstance(variants,list) or not all(isinstance(v,dict) for v in variants):
                self.issues.append({'code':'mcp_declaration','id':command['id'],'message':'variants 需要对象列表'})
                variants=[]
            for variant in [base, *({**base, **v} for v in variants)]:
                if variant.get('command') is not None and not isinstance(variant['command'],str):
                    self.issues.append({'code':'mcp_declaration','id':command['id'],'message':'变体 command 需要字符串'})
                    continue
                identity = command['namespace'] + '.' + variant['command'] if variant.get('command') else command['id']
                routes=variant.get('action_routes',{})
                if variant.get('route') not in ('query','edit','admin') or not isinstance(routes,dict) or any(r not in ('query','edit','admin') for r in routes.values()):
                    self.issues.append({'code':'mcp_route','id':identity,'message':'route/action_routes 只能指向 query/edit/admin'})
                    continue
                if not isinstance(variant.get('group','other'),str):
                    self.issues.append({'code':'mcp_declaration','id':identity,'message':'group 需要字符串'})
                    continue
                try:
                    schema = select_parameters(command['input_schema'], include=variant.get('include'), omit=variant.get('omit',[]))
                    schema['properties'].update(deepcopy(variant.get('properties',{})))
                    schema['required'] = sorted(set(schema.get('required',[])) | set(variant.get('required',[])))
                except (TypeError,ValueError,KeyError) as error:
                    self.issues.append({'code':'mcp_declaration','id':identity,'message':str(error)})
                    continue
                candidates.append(Binding(identity,command,schema,deepcopy(variant)))
        self.skills, issues = discover_skills(config.get('skills_roots'))
        self.issues.extend(issues)
        for item in self.skills:
            command = {'name':item['name'],'summary':item['summary'],'source':item['path']}
            schema = {'type':'object','properties':{'resource':{'type':'string','description':'可选技能内相对支持文件路径'}},'additionalProperties':False}
            candidates.append(Binding(item['id'],command,schema,{'route':'query','group':'skills','output':'material'},item))
        by_id = defaultdict(list)
        for binding in candidates:
            by_id[binding.id].append(binding)
        self.bindings = {}
        for identity, rows in by_id.items():
            if len(rows) != 1:
                self.issues.append({'code':'command_conflict','id':identity,'sources':[b.command.get('source') for b in rows]})
                continue
            binding = rows[0]
            enable = config['groups'].get('enable')
            if binding.id in config['disabled'] or binding.group in config['groups'].get('disable',[]) or (enable is not None and binding.group not in enable):
                binding.enabled, binding.reason = False, '在启动配置中禁用'
            self.bindings[identity] = binding
        aliases = defaultdict(list)
        for binding in self.bindings.values():
            primary = binding.id == binding.command.get('id') or binding.material is not None
            for alias in {binding.id, binding.id.rsplit('.',1)[-1],
                          binding.command.get('name') if primary else None,
                          *(binding.command.get('aliases',[]) if primary else [])} - {None}:
                aliases[alias].append(binding.id)
        self.aliases = {k:list(dict.fromkeys(v)) for k,v in aliases.items()}
        self.direct = {}
        names = defaultdict(list)
        for binding in self.bindings.values():
            exposure = config['exposure'].get(binding.id,binding.options.get('exposure','routed'))
            if exposure not in ('direct','routed'):
                self.issues.append({'code':'exposure','id':binding.id,'message':'exposure 应为 direct/routed'})
            if not binding.enabled or exposure != 'direct':
                continue
            name = binding.options.get('name', binding.id.replace('.','_').replace('-','_'))
            if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_]{1,128}', name) or name in BASE_NAMES:
                self.issues.append({'code':'direct_name','id':binding.id,'name':name,'message':'独立名称不合法或为保留名，仍可 routed 调用'})
                continue
            names[name].append(binding)
        for name, bindings in names.items():
            if len(bindings)>1:
                self.issues.append({'code':'direct_conflict','name':name,'sources':[b.id for b in bindings]})
                continue
            self.direct[name] = bindings[0]
            bindings[0].direct_name = name
        for identity in config['exposure']:
            if identity not in self.bindings:
                self.issues.append({'code':'unknown_exposure','id':identity,'message':'配置中的完整命令身份未找到'})

    def resolve(self, name, *, allow_disabled=False):
        ids = self.aliases.get(name,[])
        if name in self.bindings:
            ids = [name]
        if len(ids) != 1:
            raise InputError('命令未找到或名称有歧义',field='command',candidates=ids or get_close_matches(str(name),self.bindings,n=5))
        binding = self.bindings[ids[0]]
        if not binding.enabled and not allow_disabled:
            raise InputError('该命令在启动配置中禁用',command=binding.id)
        return binding

    def summary(self, binding):
        return {'id':binding.id,'summary':binding.summary,'group':binding.group,
                'routes':binding.routes(),'direct':binding.direct_name,'enabled':binding.enabled,
                **({'reason':binding.reason} if binding.reason else {})}
