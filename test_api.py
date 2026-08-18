#!/usr/bin/env python3
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app, search_knowledge_base

# Test search
print('=== Test Q&A ===')
results = search_knowledge_base('职工生日慰问标准是多少')
if results:
    r = results[0]
    print(f'Q: 职工生日慰问标准是多少')
    print(f'Confidence: {r["confidence"]}%')
    print(f'Source: {r["source"]}')
    print(f'Chapter: {r["chapter"]}')
    print(f'Answer (100 chars): {r["answer"][:100]}...')
print()

results2 = search_knowledge_base('三不让帮扶困难补助标准')
if results2:
    r = results2[0]
    print(f'Q: 三不让帮扶困难补助标准')
    print(f'Confidence: {r["confidence"]}%')
    print(f'Source: {r["source"]}')
    print(f'Answer (100 chars): {r["answer"][:100]}...')
print()

# Test Flask
with app.test_client() as client:
    resp = client.get('/api/health')
    print('Health:', resp.get_json())
    
    resp2 = client.post('/api/ask', json={'question': '结婚慰问标准'})
    data = resp2.get_json()
    print(f'Marriage welfare: confidence={data["confidence"]}%, source={data["source"]}')
