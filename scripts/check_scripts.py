from html.parser import HTMLParser

s = open("tmp_register.html", "r", encoding="utf-8").read()


class S(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.inp = False

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.inp = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.inp = False

    def handle_data(self, data):
        if self.inp:
            self.scripts.append(data)


p = S()
p.feed(s)
for i, code in enumerate(p.scripts):
    opens = code.count("{")
    closes = code.count("}")
    print(
        i + 1,
        "len",
        len(code),
        "opens",
        opens,
        "closes",
        closes,
        "diff",
        opens - closes,
    )
    if opens != closes:
        print("--- Script content snippet ---")
        print("\n".join(code.splitlines()[-10:]))
