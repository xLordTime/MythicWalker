"""Automated cursor ownership must never leak into manual camera control."""
import asyncio
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from adapter import WizAdapter

class Cursor:
    def __init__(self):self.active=False;self.exits=0
    async def __aenter__(self):self.active=True;return self
    async def __aexit__(self,*exception):self.active=False;self.exits+=1

class MouseControlTests(unittest.IsolatedAsyncioTestCase):
    async def test_cursor_released_on_success_error_and_cancel(self):
        adapter=WizAdapter.__new__(WizAdapter)
        cursor=Cursor();client=SimpleNamespace(mouse_handler=cursor)
        async def click():
            self.assertTrue(cursor.active);return 'clicked'
        self.assertEqual(await adapter.mouse_action(client,click),'clicked')
        self.assertFalse(cursor.active)
        async def fail():
            self.assertTrue(cursor.active);raise ValueError('Missing target')
        with self.assertRaises(ValueError):await adapter.mouse_action(client,fail)
        self.assertFalse(cursor.active)
        entered=asyncio.Event()
        async def wait():
            self.assertTrue(cursor.active);entered.set();await asyncio.Event().wait()
        task=asyncio.create_task(adapter.mouse_action(client,wait))
        await entered.wait();task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertFalse(cursor.active);self.assertEqual(cursor.exits,3)

    async def test_dialogue_click_uses_temporary_cursor(self):
        adapter=WizAdapter.__new__(WizAdapter);cursor=Cursor()
        window=SimpleNamespace(is_visible=AsyncMock(return_value=True))
        adapter.window_path=AsyncMock(return_value=window)
        async def click(target):
            self.assertIs(target,window);self.assertTrue(cursor.active)
        cursor.click_window=AsyncMock(side_effect=click)
        client=SimpleNamespace(mouse_handler=cursor,is_in_dialog=AsyncMock(return_value=True))
        self.assertTrue(await adapter.dialogue_step(client,True))
        self.assertFalse(cursor.active);self.assertEqual(cursor.exits,1)

if __name__=='__main__':unittest.main()
