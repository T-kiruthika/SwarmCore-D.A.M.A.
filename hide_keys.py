import os

def generate_safe_env():
    if not os.path.exists('.env'):
        print("❌ No .env file found!")
        return

    safe_lines = []
    with open('.env', 'r') as f:
        for line in f:
            line = line.strip()
            
            if not line or line.startswith('#'):
                safe_lines.append(line)
            
            elif '=' in line:
                key = line.split('=')[0]
                safe_lines.append(f"{key}=YOUR_{key}_HERE")
            else:
                safe_lines.append(line)

    
    with open('.env.example', 'w') as f:
        f.write('\n'.join(safe_lines))
    
    print("✅ Success! '.env.example' created automatically. Your real keys are safe.")

if __name__ == "__main__":
    generate_safe_env()