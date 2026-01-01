from pathlib import Path

p = Path(r"c:\Users\Hafidz\Desktop\Keystrokes-Dynamic\templates\register.html")
s = p.read_text(encoding="utf-8")
print("File length:", len(s))
for ch in ["{", "}", "(", ")", "[", "]", "`", '"', "'"]:
    print(ch, s.count(ch))
print("\nLast 400 chars:\n")
print(s[-400:])
# Advanced check: find last unmatched openings inside the <script> block
start = s.find("<script>")
end = s.rfind("</script>")
script = s[start : end + 9] if start != -1 and end != -1 else s
stack = []
pairs = {"}": "{", ")": "(", "]": "["}
for i, ch in enumerate(script):
    if ch in "{([":
        stack.append((ch, i))
    elif ch in "}])":
        if stack and stack[-1][0] == pairs[ch]:
            stack.pop()
        else:
            print("Unmatched closing", ch, "at index", i)
            break
if stack:
    print("\nUnmatched openings remaining:", len(stack))
    for ch, pos in stack[-5:]:
        # line number
        line = script.count("\n", 0, pos) + 1
        snippet = script[max(0, pos - 80) : pos + 80]
        print(f"Open {ch} at index {pos} (approx line {line}):\n...{snippet}...\n")
else:
    print("\nNo unmatched openings in script block")

# find last occurrence of backtick
print("\nLast backtick index:", s.rfind("`"))
# find unclosed template literal: look for odd counts of `
if s.count("`") % 2 != 0:
    print("Unbalanced backtick detected")
else:
    print("Backticks appear balanced")
