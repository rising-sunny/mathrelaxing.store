import glob
import os

def main():
    templates = glob.glob('/var/www/mathrelaxing.store/templates/*.html')
    for path in templates:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if '%.0f' in content:
            content = content.replace('%.0f', '%.2f')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated {path}")

if __name__ == "__main__":
    main()
