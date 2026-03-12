#!/usr/bin/env python3
"""
Fiber Chaos Test - Quick Test Script
快速验证分布式测试组件是否正常工作
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """测试所有导入是否正常"""
    print("Testing imports...")
    try:
        from framework.basic_fiber import FiberTest
        from framework.test_fiber import Fiber, FiberConfigPath
        from framework.util import generate_account_privakey
        print("✓ Framework imports OK")
    except Exception as e:
        print(f"✗ Framework imports failed: {e}")
        return False
    
    try:
        import flask
        import requests
        import yaml
        print("✓ External dependencies OK")
    except ImportError as e:
        print(f"✗ Missing dependency: {e}")
        print("  Run: pip3 install flask requests pyyaml")
        return False
    
    return True

def test_config_loading():
    """测试配置文件"""
    print("\nTesting config file...")
    config_path = "chaos_cluster/config.yaml"
    
    if not os.path.exists(config_path):
        print(f"✗ Config file not found: {config_path}")
        return False
    
    try:
        import yaml
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        print(f"✓ Config loaded: {len(config.get('workers', []))} workers defined")
        return True
    except Exception as e:
        print(f"✗ Config loading failed: {e}")
        return False

def test_file_structure():
    """测试文件结构"""
    print("\nTesting file structure...")
    
    required_files = [
        "chaos_cluster/master_node.py",
        "chaos_cluster/worker_node.py",
        "chaos_cluster/deploy.sh",
        "chaos_cluster/config.yaml",
        "chaos_cluster/README.md",
        "framework/basic_fiber.py",
        "framework/test_fiber.py",
    ]
    
    all_ok = True
    for file in required_files:
        if os.path.exists(file):
            print(f"✓ {file}")
        else:
            print(f"✗ {file} (missing)")
            all_ok = False
    
    return all_ok

def test_syntax():
    """测试Python文件语法"""
    print("\nTesting Python syntax...")
    import py_compile
    
    files = [
        "chaos_cluster/master_node.py",
        "chaos_cluster/worker_node.py",
    ]
    
    all_ok = True
    for file in files:
        try:
            py_compile.compile(file, doraise=True)
            print(f"✓ {file}")
        except Exception as e:
            print(f"✗ {file}: {e}")
            all_ok = False
    
    return all_ok

def main():
    print("="*60)
    print("Fiber Chaos Test - Quick Verification")
    print("="*60)
    
    results = []
    results.append(("File Structure", test_file_structure()))
    results.append(("Imports", test_imports()))
    results.append(("Config", test_config_loading()))
    results.append(("Syntax", test_syntax()))
    
    print("\n" + "="*60)
    print("Summary")
    print("="*60)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{name:20} {status}")
    
    all_passed = all(passed for _, passed in results)
    
    if all_passed:
        print("\n✓ All checks passed! Ready to deploy.")
        print("\nNext steps:")
        print("  1. Deploy Master: ./chaos_cluster/deploy.sh --mode master")
        print("  2. Deploy Workers on other machines")
        print("  3. Monitor: curl http://master:5000/api/status")
    else:
        print("\n✗ Some checks failed. Please fix the issues above.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
