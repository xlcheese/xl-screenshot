import helpers  # paths, a temporary home folder, English
"""The app's own English text uses US spelling (xlcheese/xl-screenshot#4)."""
import os, re
pot = open(os.path.join(helpers.ROOT, "po", "xl-screenshot.pot"), encoding="utf-8").read()
# every English phrase: msgid lines, and the continuation lines of long ones
english = " ".join(a or b for a, b in re.findall(r'^msgid "(.*)"$|^"(.*)"$', pot, re.M))
fails = []
def check(n, c): print(("PASS " if c else "FAIL ") + n); c or fails.append(n)
check("the template has the app's text", "Screenshot" in english and len(english) > 2000)
british = {"colour": "color", "centre": "center", "grey": "gray", "behaviour": "behavior",
           "recognis": "recogniz", "favour": "favor", "licence": "license", "cancelled": "canceled"}
for uk, us in british.items():
    found = re.findall(rf"\b\w*{uk}\w*", english, re.I)
    check(f"no '{uk}' (US: '{us}') in the app's text" + (f": {sorted(set(found))}" if found else ""), not found)
print("FAILURES:", fails or "none")
