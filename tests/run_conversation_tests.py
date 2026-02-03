#!/usr/bin/env python3
"""Simple test runner for conversation tests"""
import sys
import os

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import unittest
from test_conversation import TestConversationDB, TestConversationManager, TestConversationJSONHandler

# Create test suite
loader = unittest.TestLoader()
suite = unittest.TestSuite()

suite.addTests(loader.loadTestsFromTestCase(TestConversationDB))
suite.addTests(loader.loadTestsFromTestCase(TestConversationManager))
suite.addTests(loader.loadTestsFromTestCase(TestConversationJSONHandler))

# Run tests
runner = unittest.TextTestRunner(verbosity=1)
result = runner.run(suite)

# Print summary
print('\n=== Test Summary ===')
print(f'Tests run: {result.testsRun}')
print(f'Failures: {len(result.failures)}')
print(f'Errors: {len(result.errors)}')

# Exit with appropriate code
sys.exit(0 if result.wasSuccessful() else 1)
