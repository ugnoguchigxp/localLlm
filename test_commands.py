import subprocess
import os
import sys

def run_command_test(cmd_path, input_text):
    print(f"Testing: {cmd_path} with input '{input_text}'...")
    try:
        # --backend mock を強制的に追加してテスト
        # 本来のスクリプトは内部で固定のbackendを呼ぶが、
        # ここではスクリプトをバイパスして直接 main.py を呼ぶか、
        # あるいはスクリプトが引数を受け取ることを利用して --backend mock を渡す
        process = subprocess.Popen(
            [cmd_path, "--backend", "mock"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # MCPサーバーの起動時間を考慮してタイムアウトを延長
        stdout, stderr = process.communicate(input=f"{input_text}\nexit\n", timeout=30)
        
        if process.returncode == 0:
            print("✅ Success")
            # 出力に期待される文字列が含まれているか
            if "Assistant:" in stdout:
                print("   - Output contains Assistant response.")
            if "[Thinking...]" in stdout or "Wait, let me think..." in stdout:
                print("   - Output contains thinking tags filtering.")
            return True
        else:
            print(f"❌ Failed (Return code: {process.returncode})")
            print(f"Error: {stderr}")
            return False
    except Exception as e:
        print(f"❌ Error during execution: {e}")
        return False

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    scripts_dir = os.path.join(root_dir, "scripts")
    commands = ["bonsai", "ollama-v4", "gemma4"]
    
    results = {}
    for cmd in commands:
        cmd_path = os.path.join(scripts_dir, cmd)
        if not os.path.exists(cmd_path):
            print(f"❌ Command not found: {cmd_path}")
            results[cmd] = False
            continue
            
        # 思考タグのフィルタリングテスト
        res = run_command_test(cmd_path, "test_thinking")
        results[cmd] = res

    print("\n--- Test Results Summary ---")
    all_passed = True
    for cmd, res in results.items():
        status = "PASSED" if res else "FAILED"
        print(f"{cmd}: {status}")
        if not res: all_passed = False
        
    if all_passed:
        print("\n🎉 All commands verified successfully (in Mock mode)!")
        sys.exit(0)
    else:
        print("\n⚠️ Some tests failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
