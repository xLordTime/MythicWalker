import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from settings import DEFAULTS,Settings,migrate,validate
from server import Bridge
from adapter import DemoAdapter
from widget import StatusWidget

class WidgetSettingsTests(unittest.TestCase):
    def test_conflicts_validation_migration_and_persistence(self):
        value=copy.deepcopy(DEFAULTS);value['bindings']['scan']='F10'
        with self.assertRaises(ValueError):validate(value)
        del value['widget'];old=migrate(value)
        self.assertEqual(old['bindings']['scan'],'F10');self.assertEqual(old['widget']['hotkey'],'')
        value=copy.deepcopy(DEFAULTS);value['widget'].update(hotkey='ctrl + F10',start_hidden=True,topmost=False)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json';Settings(path).save(value)
            self.assertEqual(Settings(path).data['widget'],{'hotkey':'Ctrl+F10','start_hidden':True,'topmost':False})
        value['widget']['start_hidden']=1
        with self.assertRaises(ValueError):validate(value)
    def test_cross_thread_commands_are_queued(self):
        widget=StatusWidget('test');config=copy.deepcopy(DEFAULTS['widget'])
        widget.configure(config);config['hotkey']=''
        self.assertEqual(widget.events.get_nowait(),('configure',DEFAULTS['widget'],''))
        widget.visibility('hide');self.assertEqual(widget.events.get_nowait(),('visibility','hide',''))

class WidgetBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_hidden_widget_does_not_stop_hook_or_automation(self):
        widget=Mock();bridge=Bridge(DemoAdapter(),'test',[],True,widget=widget)
        await bridge.dispatch('hook',{'ids':['9001']})
        await bridge.dispatch('widget',{'action':'hide'})
        widget.visibility.assert_called_once_with('hide')
        self.assertTrue(bridge.adapter.rows[0]['hooked'])
        value=copy.deepcopy(DEFAULTS);value['widget']['hotkey']='Ctrl+F10'
        await bridge.dispatch('set_settings',{'settings':value})
        widget.configure.assert_called_with(value['widget'])
        with self.assertRaises(ValueError):await bridge.dispatch('widget',{'action':'delete'})
        cli=Bridge(DemoAdapter(),'test',[],True)
        with self.assertRaises(ValueError):await cli.dispatch('widget',{'action':'show'})
