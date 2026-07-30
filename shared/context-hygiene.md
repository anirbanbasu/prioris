# Shared: Context Window Hygiene

Referenced by `../skills/discuss`, `../skills/quick-read`, `../skills/quiz-me`, `../skills/reading-log`.

## When to nudge

Full paper text and back-and-forth discussion fill a context window fast — a single 30-page paper is already roughly 15-25K tokens, and many of the models this plugin runs on cap out at 256K tokens or less. Once a conversation has been running for a while (many turns, or more than a couple of papers/topics touched), politely remind the user that continuing to discuss papers in the same session will keep eating into that budget, and suggest they clear or start a fresh context before the next paper or topic.

Keep the nudge to a sentence, place it at the end of your response (never mid-discussion), and don't repeat it every turn — once per long-running stretch is enough. This is a suggestion, not an action taken on the user's behalf: never clear or reset context yourself.
