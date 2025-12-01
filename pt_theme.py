import sys
import os

# Auto-activate venv if not already active
if sys.prefix == sys.base_prefix:
    # Assuming 'venv' is in the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(script_dir, "venv", "bin", "python")
    
    # If not found, check current working directory
    if not os.path.exists(venv_python):
         venv_python = os.path.join(os.getcwd(), "venv", "bin", "python")

    if os.path.exists(venv_python):
        # Re-execute the script with the venv python
        os.execv(venv_python, [venv_python] + sys.argv)

import random
import time
import sys
import webbrowser

# === ANSI COLORS ===
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"

# === Typing Animation ===
def type_out(text, delay=0.002):
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()

# === PR DETAILS (Dynamic inputs in your automation) ===
pr_id = "121338"
title = "ADW-1245 [Merkle] master ➜ dev"
status = "ACTIVE"
source = "master"
target = "dev"
pr_link = "https://dev.azure.com/mpcoderepo/DigitalExperience/_git/aemaacs-life/pullrequest/121338"

# === RANDOM TITLES ===
titles = [
    "⚡ CODE LEGEND — PULL REQUEST INITIATED! ⚡",
    "🦸‍♀️ DEPLOYMENT HERO — MISSION UNDERWAY! 🦸‍♀️",
    "🚀 MERGE COMMANDER — OPERATION SUCCESS! 🚀",
    "🔥 BUILD WARRIOR — PR VICTORY UNLOCKED! 🔥",
    "💾 REPO GUARDIAN — CODE DEFENDED! 💾",
    "🌌 MASTER OF MERGES — PORTAL OPENED! 🌌",
    "🧠 SYNCHRONIZATION COMPLETE — CODE HARMONY ACHIEVED 🧠",
    "🎮 GIT HERO — LEVEL UP UNLOCKED! 🎮",
    "💫 COSMIC COMMITTER — MISSION LOG UPDATED 💫",
    "🛠️ REPOSITORY AVENGER — CLEAN CODE DEPLOYED 🛠️",
    "👑 CODE CONQUEROR — BRANCHES UNITED 👑",
    "🧑‍🚀 LAUNCH SEQUENCE COMPLETE — READY FOR REVIEW 🧑‍🚀",
]

# === THEMES ===
themes = [
    f"""{YELLOW}
🔥🦸  {BOLD}AVENGERS INITIATIVE: CODE ASSEMBLE!{RESET}
💥 Another PR lands like Mjölnir striking the repo!
🧪 Mission: {source} ➜ {target}
📋 PR ID: {pr_id} | Title: {title} | Status: {status}
💬 Tony Stark: “Code like you mean it. Review like you own it.”
🚀 {pr_link}
💡 Tip: “Whatever it takes... to merge that PR.”
""",
    f"""{BLUE}
🌠🛸  {BOLD}STAR WARS: THE CODE AWAKENS{RESET}
🚀 A long time ago, in a repo far, far away…
🎯 Target: {target} | Source: {source}
🆔 PR: {pr_id} | Status: {status}
🧙 Obi-Wan: “Use the Force of clean commits.”
✨ {pr_link}
💫 “In the end... the PR merges you.”
""",
    f"""{GREEN}
💾🕶️  {BOLD}THE MATRIX: ENTER THE MERGE{RESET}
⛓️ You didn’t just push code — you bent Git to your will.
📋 {title} [{source} ➜ {target}]
💬 Morpheus: “There is no spoon. Only the merge.”
🧠 Code coverage rising... build stable...
🔗 {pr_link}
🕶️ “Wake up, dev. The repo is real.”
""",
    f"""{MAGENTA}
🦇🌃  {BOLD}BATMAN: THE DARK MERGE{RESET}
💻 Gotham Repo: {source} ➜ {target}
🆔 Case File: {pr_id}
🦸 “It’s not who I am underneath, but what I merge that defines me.”
🔗 {pr_link}
💀 Justice... and clean code.
""",
    f"""{RED}
🍄🎮  {BOLD}SUPER MERGIO BROS!{RESET}
🎯 Source: {source} ➜ {target} | PR ID: {pr_id}
🎉 “It’s-a merge time!” 
🏁 Princess Build Success is in another pipeline.
🔗 {pr_link}
⭐ “Let’s-a deploy!”
""",
    f"""{CYAN}
🌃⚡  {BOLD}CYBERPUNK 2099: NEON CODE DEPLOY{RESET}
💾 {title}
🧠 {source} ➜ {target} | PR: {pr_id}
👁️ “You don’t commit... you inject code into the system.”
💫 {pr_link}
🌌 “Wake up, dev. The repo is calling.”
""",
    f"""{YELLOW}
💍🧙  {BOLD}LORD OF THE COMMITS{RESET}
🧠 Gandalf: “Fly, you fools... and push to {target}!”
🔥 PR: {pr_id} | {title}
🧿 The Eye of Jenkins sees all...
🌋 {pr_link}
⚔️ “One merge to rule them all.”
""",
    f"""{MAGENTA}
☠️⚓  {BOLD}PIRATES OF THE CODEBEAN: MERGE TIDE{RESET}
🏴‍☠️  Source: {source} ➜ {target}
🪙  Treasure Map (PR ID): {pr_id}
🍻  “A smooth merge never made a skilled coder.”
🦜 {pr_link}
💀 Yo-ho-ho and a clean build too!
""",
    f"""{GREEN}
💻🕷️  {BOLD}HACKER UNDERGROUND: PROTOCOL INITIATED{RESET}
🧠 Commit Trace: {title}
🕶️ Target Node: {target}
⚡ Merge infiltration complete.
💣 {pr_link}
🕷️ “Hack the code. Free the repo.”
""",
    f"""{YELLOW}
🔥💫  {BOLD}DRAGON BALL: MERGE Z!{RESET}
💥 Power level... OVER 9000!
🏆 PR ID: {pr_id} | {source} ➜ {target}
Goku: “This merge… it’s destiny.”
🌟 {pr_link}
💫 “Merge now… feel the ki!”
""",
    f"""{BLUE}
🚀🌌  {BOLD}NASA MISSION CONTROL{RESET}
🛰️ Launch Sequence: {title}
🌍 From {source} ➜ {target} | PR ID: {pr_id}
🧑‍🚀 Houston: “We have a successful merge.”
🔭 {pr_link}
🌠 “Failure is not an option (except in tests).”
""",
    f"""{RED}
🕹️👾  {BOLD}RETRO ARCADE: INSERT MERGE COIN{RESET}
🎮 PR ID: {pr_id} | {source} ➜ {target}
💾 Saving progress...
🏁 Level Complete: {title}
🔗 {pr_link}
🧩 “Achievement Unlocked: Clean Commit.”
"""
]

# === Randomly Pick Header and Theme ===
chosen_title = random.choice(titles)
chosen_theme = random.choice(themes)

# === Animated Header ===
header = f"""{CYAN}{BOLD}
══════════════════════════════════════════════════════════════════════
       {chosen_title}
══════════════════════════════════════════════════════════════════════
{RESET}"""

# === Print Animated Cinematic Message ===
type_out(header, 0.001)
time.sleep(0.5)
type_out(chosen_theme, 0.001)
time.sleep(0.3)

# === Final Interactive Message ===
print(f"{GREEN}{BOLD}🌟 Great work, hero! Opening PR in browser... 🌟{RESET}")
time.sleep(1)
webbrowser.open(pr_link)
