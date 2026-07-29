import json
import re

transcript_path = r"C:\Users\gawan\.gemini\antigravity\brain\d1ba81c0-0775-4eb0-b5c0-4d5fbe0aa500\.system_generated\logs\transcript_full.jsonl"

def reconstruct_file(target_file_name, output_dest):
    print(f"Reconstructing {target_file_name}...")
    lines_dict = {}
    
    with open(transcript_path, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            # We only want to look at VIEW_FILE type steps before we started editing in this session.
            # Our first edit to Dashboard.tsx was step 358. Our first edit to Logs.tsx was step 380.
            # So looking at steps <= 380 is perfect!
            step_index = data.get("step_index")
            if step_index > 380 and target_file_name == "Dashboard.tsx":
                continue
            if step_index > 390 and target_file_name == "Logs.tsx":
                continue
                
            if data.get("type") == "VIEW_FILE":
                content = data.get("content", "")
                if target_file_name in content:
                    # Extract lines from content
                    # Format is usually: "123: line_content\n"
                    for file_line in content.split("\n"):
                        match = re.match(r"^(\d+):\s(.*)$", file_line)
                        if match:
                            line_num = int(match.group(1))
                            line_content = match.group(2)
                            lines_dict[line_num] = line_content
                            
    if not lines_dict:
        print(f"Error: No lines found for {target_file_name}")
        return
        
    max_line = max(lines_dict.keys())
    print(f"Found {len(lines_dict)} lines out of max line {max_line}")
    
    # Let's check for missing lines
    missing = []
    for i in range(1, max_line + 1):
        if i not in lines_dict:
            missing.append(i)
            
    if missing:
        print(f"Warning: Missing lines: {missing}")
    
    # Write to destination
    with open(output_dest, "w", encoding="utf-8") as out:
        for i in range(1, max_line + 1):
            out.write(lines_dict.get(i, "") + "\n")
    print(f"Successfully wrote reconstructed file to {output_dest}")

reconstruct_file("Dashboard.tsx", r"c:\Users\gawan\OneDrive\Desktop\temp project\cctv project\src\pages\Dashboard.tsx")
reconstruct_file("Logs.tsx", r"c:\Users\gawan\OneDrive\Desktop\temp project\cctv project\src\pages\Logs.tsx")
