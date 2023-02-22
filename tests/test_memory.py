import unittest
from utils.memory import Memory


class TestMemory(unittest.TestCase):
    def setUp(self):
        self.memory = Memory()

    def test_append(self):
        self.memory.append("user1", "Hello")
        self.memory.append("user1", "World")
        self.assertEqual(self.memory.storage["user1"], ["Hello", "World"])

    def test_get(self):
        self.memory.append("user1", "Hello")
        self.memory.append("user1", "World")
        self.assertEqual(self.memory.get("user1"), "Hello\n\nWorld")

    def test_remove(self):
        self.memory.append("user1", "Hello")
        self.memory.remove("user1")
        self.assertEqual(self.memory.get("user1"), "")