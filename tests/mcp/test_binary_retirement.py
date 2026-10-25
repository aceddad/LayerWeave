"""真实 MCP JSON 边界的二进制往返、分页、冲突和退役历史。"""
import asyncio
import base64
import json
import unittest
from unittest.mock import patch

from tests._support.mcpfixture import MCPFixture, HAS_MCP
from layerweave.support.api import register_tables, unregister_tables, read_record
from layerweave.support.feedback import InputError


@unittest.skipUnless(HAS_MCP, '安装 layerweave[mcp] 运行可选协议验收')
class BinaryMCPTests(MCPFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        register_tables(self.c, {"binary_cache": {"fields": {"payload": "BLOB", "text": "TEXT"}}})

    def create(self, value="AAH/"):
        return self.call('edit', 'dispatch', request={'action': 'create', 'kind': 'binary_cache',
            'project_id': self.project, 'data': {'payload': value}})['result']

    def test_payload_and_undo_conflicts_are_json(self):
        made = self.create()
        self.assertEqual(made['data']['payload'], 'AAH/')
        self.assertEqual(read_record(self.c, 'binary_cache', project_id=self.project, id=made['id'])['payload'], b'\x00\x01\xff')
        request = {'action': 'update', 'kind': 'binary_cache', 'project_id': self.project, 'id': made['id']}
        changed = self.call('edit', 'dispatch', request={**request, 'data': {'payload': 'eA=='}})['result']
        self.call('edit', 'dispatch', request={**request, 'data': {'payload': 'eQ=='}})
        failed = self.runtime.invoke('edit', 'undo_operation', {'operation_id': changed['operation_id']})
        self.assertTrue(failed.is_error)
        self.assertEqual(failed.data['result']['error']['code'], 'undo_conflict')
        self.assertEqual(failed.data['result']['error']['conflicts'][0]['current']['payload'], 'eQ==')
        json.dumps(failed.data)

    def test_history_and_exchange_after_retirement(self):
        made = self.create()
        exported = self.call('query', 'export_project')['result']
        record = next(item for item in exported['records'] if item['kind'] == 'binary_cache')
        self.assertEqual(record['data']['payload'], 'AAH/')
        unregister_tables(self.c, ['binary_cache'])
        history = self.call('query', 'read_history', operation_id=made['operation_id'])['result']
        self.assertEqual(history['items'][0]['changes'][0]['after']['payload'], 'AAH/')
        failed = self.runtime.invoke('edit', 'undo_operation', {'operation_id': made['operation_id']})
        self.assertEqual(failed.data['result']['error']['code'], 'retired_kind')
        invalid = self.runtime.invoke('edit', 'import_project', {'document': exported})
        self.assertEqual(invalid.data['result']['error']['code'], 'retired_kind')

    def test_large_blob_pages_and_error_details_serialize(self):
        encoded = base64.b64encode(bytes(range(256)) * 16).decode('ascii')
        made = self.create(encoded)
        # Creation may itself be paginated. Read the record again with bounded output.
        id = read_record(self.c, 'binary_cache', project_id=self.project)[0]['id']
        result = self.runtime.invoke('query', 'dispatch', {'request': {'action': 'read', 'kind': 'binary_cache',
            'project_id': self.project, 'id': id}}, max_chars=1024)
        self.assertFalse(result.is_error, result.data)
        self.assertFalse(result.data['result_complete'])
        parts = []
        while True:
            parts.append(result.data['fragment']['text'])
            cursor = result.data['more']['cursor']
            if cursor is None:
                break
            result = self.runtime.continue_result(cursor)
            self.assertFalse(result.is_error, result.data)
        restored = json.loads(''.join(parts))
        self.assertEqual(restored['result']['data']['payload'], encoded)
        with patch.object(self.runtime, '_call', side_effect=InputError('binary diagnostic', value=b'\xff')):
            failed = self.runtime.invoke('query', 'dispatch', {'request': []})
        self.assertEqual(failed.data['error']['value'], '/w==')
        json.dumps(failed.data)

    def test_real_sdk_structured_content_and_text_match(self):
        from mcp import Client
        from layerweave.tool.builtin.shared.mcp import create_server
        async def check():
            async with Client(create_server(self.runtime)) as client:
                reply = await client.call_tool('layerweave_edit', {'command': 'dispatch', 'arguments': {
                    'request': {'action': 'create', 'kind': 'binary_cache', 'project_id': self.project,
                                'data': {'payload': 'AAH/'}}}})
                self.assertFalse(reply.is_error, reply.structured_content)
                self.assertEqual(reply.structured_content['result']['data']['payload'], 'AAH/')
                self.assertEqual(json.loads(reply.content[0].text), reply.structured_content)
        asyncio.run(check())
