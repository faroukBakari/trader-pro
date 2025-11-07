Beyond the Monolith: Re-Architecting
GitHub Copilot Instructions for Agentic,
TDD-Driven Workflows
A Technical Deep-Dive into Modular Customization, Prompt Engineering, and Agentic
State Management
Deconstructing the Monolithic Instruction Set: An
Architectural Analysis
The provided .github/copilot-instructions.md file represents a sophisticated attempt to
enforce a complex, multi-step development methodology upon an AI agent. However, its
effectiveness is critically undermined by three foundational issues rooted in a
misunderstanding of how Large Language Models (LLMs) and the GitHub Copilot service
fundamentally operate. The file's design is architecturally unsound, leading to
non-compliance not out of AI "disobedience," but as a predictable outcome of its structure.
The "Lost in the Middle" Problem: Prompt Bloat and Attention Dilution
The instruction set is exceptionally long, attempting to define a persona, a multi-phase TDD
workflow, file-handling rules, and immutable principles within a single, monolithic document.
This design philosophy is a primary source of failure.
LLMs, which are based on Transformer architectures, suffer from a well-documented
phenomenon known as the "Lost in the Middle" effect.1 While their theoretical context
windows are large, their practical "attention" is not evenly distributed. Models tend to place
higher recall priority on information presented at the very beginning and very end of a prompt,
with information in the middle having a significantly higher chance of being ignored or
"forgotten".1
The provided prompt's most critical section, the MANDATORY: TDD & Feature Workflow, is
buried deep in the middle of the document, making it a prime candidate for this "attention
dilution".4 This is not a theoretical risk; it is a common failure mode. Community reports
confirm this behavior: one user with a similarly complex, 9,000-token instruction file reported
that as the file grew, Copilot responses became slower and the agent began to loop or repeat
tasks unnecessarily.5
This degradation is supported by technical research, which indicates that LLM reasoning
performance begins to decline at input lengths as short as 3,000 tokens.6 Beyond this point,
additional context risks becoming "noise rather than signal," increasing the chance of
hallucination and instruction-following failure.7 The user's attempt to be exhaustive is the
primary reason the prompt is failing; its length is actively harming the AI's ability to follow its
content.
The Myth of Emphatic Syntax: !!CRITICAL!! vs. Probabilistic
Compliance
The instruction file is replete with emphatic syntax: !!CRITICAL!!, !!IMPORTANT!!,
⚠⚠
, and
MANDATORY. This is a common "folk remedy" in prompt engineering, stemming from the
correct observation that LLMs, trained on natural language, recognize capitalization and
emphasis as signals of importance.8 This syntax can help the model "assign weight" to
specific concepts.10
However, this is a soft influence, not a hard constraint. An LLM is a probabilistic system that
generates the next most likely token; it is not a deterministic computer program that executes
a !!CRITICAL!! instruction with 100% compliance. This emphasis is competing for "attention"
with the prompt bloat (see 1.1) and, more importantly, with the model's own training.
If an instruction is mechanically complex (like a multi-step workflow) or contradicts the AI's
standard training patterns, no amount of emphasis will force compliance. A 2025 study
evaluating Copilot's code review feature provided a stark example: despite its purpose,
Copilot was found to "frequently fail to detect critical vulnerabilities" such as SQL injection.11 If
the agent can fail at a core, security-centric task, it will certainly fail to follow a bespoke,
complex, multi-step TDD workflow, regardless of the number of
⚠
emojis. The user is
attempting to fix a deep structural problem (an impossible workflow) with a stylistic solution
(emphatic syntax), which will invariably fail.
Re-evaluating the Token Budget: 1,000,000 Tokens vs. Practical
Reality
The instruction file's ## 7. Token Budget section, which specifies "1,000,000 tokens," is
based on a fundamental misinterpretation of Copilot's service architecture. This figure
appears to be anchored on the marketing of a specific model's (e.g., Gemini 2.5) theoretical
context window 12, not the practical limits of the GitHub Copilot service.
The actual context window for GitHub Copilot Chat is 64k tokens (using GPT-4o) for standard
users, with a 128k token window available in VS Code Insiders as of late 2024.13 This is a
fraction of the 1,000,000-token "budget" set in the file. GitHub's own staff have explicitly
confirmed that the Copilot service does not support the full 1M token window, even if the
underlying model does.12
Furthermore, Microsoft's own practical guidance for its Copilot products advises much
smaller, functional limits. For example, it suggests that "rewrite works best on a document that
is less than about 3,000 words".14 This false belief in a 1,000,000-token budget is precisely
what enables the "prompt bloat" identified in section 1.1. A new architecture must be built for
the 64k-128k reality, where every token matters and bloat is the primary antagonist.7
The "Stateful Agent" Fallacy: Why Your TDD Workflow
Is Architecturally Impossible
The core MANDATORY: TDD & Feature Workflow is the most significant flaw in the instruction
set. It attempts to program a deterministic, stateful workflow into a system that is, by design,
stateless. This section of the prompt is not just ineffective; it is architecturally impossible for
the Copilot Chat model to execute as written.
"Wait for Approval": A Workflow Primitive, Not a Prompt Instruction
The prompt explicitly commands the AI: "After proposing a plan... you must stop and wait for
explicit user approval before proceeding."
This instruction is mechanically impossible for an LLM to follow. In a chat interface, an LLM
call is a stateless computation. It receives a single, complete context (the system prompt +
chat history) and produces a single, complete response. It cannot "stop" its text generation
mid-way, "wait" indefinitely for an external human signal, and then "resume" the same
generation task.
The concept of "waiting for approval" is a problem of state management.16 In software
engineering, this "human-in-the-loop" pattern is handled by an external orchestrator, not by
the worker (the LLM) itself. This is precisely how such features are implemented in the real
world:
● GitHub Actions: A workflow_dispatch or environment protection can "wait for approval,"
which halts the external CI/CD runner.18
● Agentic Frameworks: Systems like LangGraph are explicitly designed as state machines
to manage multi-step workflows, where a "wait" is a specific node in a graph that pauses
the orchestration and waits for new input.17
The user has confused a system prompt with an orchestration script. The
copilot-instructions.md file provides initial context to the LLM worker; it is not a script that
executes a multi-step workflow. This command will always be ignored because the model is
incapable of performing the action.
Forcing Determinism on a Probabilistic Model: A Flawed TDD
Approach
The provided workflow is a rigid, linear, "Analysis First" process: Step 0: Analysis -> Phase 1:
Planning -> `` -> Phase 2: Red -> Phase 3: Green -> Phase 4: Refactor. This is not only
impossible to enforce (per 2.1) but is also counter-productive to the stated goal of a "TDD &
Feature Workflow."
The documented strengths of Copilot in TDD are in the rapid, iterative "Red-Green-Refactor"
loop, which is driven by the human.22 The effective workflow is:

1. Red: The human writes a failing test.
2. Green: The human prompts Copilot (e.g., inline chat) to "make this test pass." Copilot
   excels at this, as its strength is generating repetitive code.24
3. Refactor: The human selects the new code and prompts Copilot to "/fix" or "refactor this
   to be more efficient".24
   The user's workflow explicitly prevents this. By forcing a mandatory "Analysis First" planning
   phase and forbidding the AI from proceeding without approval, it neuters Copilot's primary
   TDD strength. It forces the AI to be a high-level planner when its true value in TDD is as a
   low-level, high-speed "typist" in the iterative loop. One study that attempted to automate TDD
   with agents noted this exact problem, finding that "Agent mode occasionally deviated from
   the TDD development model, possibly due to the design of the prompts".25
   The user is forcing a human-centric, waterfall "Analysis First" model onto an AI tool that excels
   at agile iteration. The workflow is not only impossible to enforce but is also the wrong
   workflow for AI-assisted TDD.
   A New Architecture: Migrating from a Monolithic to a
   Modular Customization System
   The intent behind the monolithic prompt is correct: to create a specialized, context-aware AI
   partner. The implementation is flawed. The solution is to migrate this intent from the single,
   failing file into the modern, modular GitHub Copilot customization ecosystem. This involves
   decomposing the monolith into three distinct, specialized components.
   The Foundation (Level 1): The New copilot-instructions.md
   The first step is to gut the existing copilot-instructions.md file, reducing its size by ~90% and
   repurposing it for its one correct function: providing globally-applied, high-level context that
   applies to all chat requests.26
   This file becomes the project's "Constitution."
   ● Content to Keep:
   ○ Persona: The ## 1. Role and Core Directives section is a perfect use case. Assigning
   a persona like "expert full-stack developer" is a known best practice.24
   ○ High-Level Principles: Simple, immutable rules like "Write Clean Code," "Use Open
   Standards," and especially the rule: "Comments in source code are only for
   planning (TODO, FIXME), never for general explanation." This rule is an
   exemplary instruction—clear, high-level, and globally applicable.
   ● Content to Remove:
   ○ All !!CRITICAL!! preambles (ineffective, see 1.2).
   ○ The entire ## 2. The TDD & Feature Workflow (will be migrated, see 3.2).
   ○ The ## 7. Token Budget (factually incorrect, see 1.3).
   ● Content to Add:
   ○ As per expert recommendations, this file should include "Tech Stack" and "Key
   Resources" sections.29 This is where documentation is referenced using Markdown
   links, not commands.27
   On-Demand Execution (Level 2): Migrating Workflows to prompt files
   The complex, multi-step ## 2. The TDD & Feature Workflow should be migrated to a prompt
   f
   ile. Prompt files are Markdown files stored in .github/prompts/ and are designed for reusable,
   on-demand, specific tasks.31 They are the "Toolbox" or "Macros" of the Copilot system.
   This file (e.g., .github/prompts/tdd-plan.md) is triggered by the user typing /tdd-plan in the
   chat window.31
   This migration solves the "Wait for Approval" problem. The new workflow becomes:
4. The user wants to start a new feature. They type /tdd-plan and describe the feature.
5. The tdd-plan.md prompt file is activated. Its new, focused instruction is: "Your goal is to
   generate a detailed plan following this TDD workflow. Analyze the user's request and the
   @workspace context, and output only the plan. Do not write any code."
6. The AI executes this single, focused task: it generates the plan and then stops.
7. The user is now, naturally, in the "approval" step. They are the human-in-the-loop
   orchestrator.17 They can review the plan and then begin the actual TDD loop by
   prompting, "OK, implement Step 1: Write the failing test."
   This architecture replaces the impossible programmatic wait with a natural, human-driven
   workflow.
   Specialized Personas (Level 3): Using chat modes (or "Agents") for
   Advanced States
   Finally, the user's monolithic persona (Full-stack, DevOps, TDD, Data) should be split into
   custom chat modes. Chat modes (which are conceptually merging with "Agents") 34 are
   specialized personas that bundle their own instructions and a curated set of tools.35 This is
   the true path to an "expert pair-programmer".38
   Instead of one confused "jack-of-all-trades" agent, the user can create specialists:
   ● devops-partner.md: A chat mode whose instructions are "You are a DevOps expert. You
   only care about CI/CD, GitHub Actions, and automation." This mode could be configured
   to only have access to the @terminal 44 and the ability to read _.yml files.
   ● db-designer.md: A chat mode focused only on "data modeling" and reading schema.rb
   or docs/db-schema.md.
   The user can then switch to the "DevOps Agent" when they need DevOps help, and that agent
   will have a focused, clean context only for that task. This modular system of specialized
   agents (chat modes) supported by a library of tools (prompt files) is the correct, modern, and
   functional architecture for this use case.
   A Comparative Guide to the GitHub Copilot
   Customization Ecosystem
   To implement this new architecture, it is essential to understand the distinct purpose of each
   customization file. The user's core problem was tool confusion—using the global instruction
   f
   ile for all three tasks. The following table provides a new mental model for which tool to use
   and when.
   Customization
   Tool
   Global
   Instructions
   Path-Specific
   Instructions
   File Location(s)
   .github/copilot-instr
   uctions.md
   Activation &
   Scope
   Automatic: Applies
   to all chat requests
   in the workspace.
   Primary Use Case
   (The "When-To")
   The
   "Constitution": Set
   the core persona,
   high-level
   principles, tech
   stack, and
   immutable rules for
   the project.26
   .github/instructions
   /_.instructions.md
   Automatic
   (Path-Based):
   Applies only when
   The "Linter":
   Enforce
   context-specific
   Copilot is
   interacting with
   files matching a
   glob pattern.26
   standards. (e.g.,
   "For **/\*.rb files,
   use Minitest" or
   "For **/_.css, use
   BEM notation").
   Prompt Files .github/prompts/_.
   md
   On-Demand
   (User-Triggered):
   User must type
   /my-prompt-name
   in chat.31
   The "Toolbox /
   Macro": Execute
   specific, complex,
   repeatable tasks.
   (e.g., /tdd-plan,
   /generate-compon
   ent). This is the
   correct migration
   path for the TDD
   workflow.
   Chat Modes /
   Agents
   .github/chatmodes/
   \*.md (or
   AGENTS.md)
   On-Demand
   (User-Selected):
   User selects a
   "persona" from the
   chat dropdown.35
   The "Specialist":
   Create a
   specialized agent
   with its own
   instructions and
   curated set of
   tools. (e.g.,
   "Security Reviewer
   Agent," "DevOps
   Agent").

Optimized Prompting Standards and Context
Management (The New "Best Practices")

Migrating to the modular architecture also requires adopting modern, explicit syntax for
context management. The user's prompt attempts to command the AI to find context; the
correct approach is to provide the context directly.

Dynamic Context: Replacing "Analysis First" with @workspace and
#file
The user's Analysis First directive ("You must never guess") is a symptom of Copilot lacking
context. The solution is not to prohibit guessing, but to provide context so guessing is not
required.
The user's entire Step 0: Analysis section is an attempt to prompt-engineer a feature that
already exists: the @workspace participant.
● @workspace: This command automatically provides context from the entire codebase.39
It scans the directory structure, indexed files, and symbols to build a holistic
understanding.39 The new /tdd-plan prompt file, for example, should begin with "Analyze
the user's request using @workspace to understand the existing code..." This single
keyword is more powerful and reliable than the user's entire multi-paragraph "Analysis"
instruction.
● #file:: For explicit context, the user can reference specific files using the
#file:'path/to/file.md' syntax.41 This is infinitely more reliable than hoping the AI reads the
correct file.
Referencing Documentation: From Command to Context
The user's instruction "ALWAYS read docs/DOCUMENTATION-GUIDE.md FIRST" is a
"hope-based" prompt that will be ignored due to the "Lost in the Middle" effect.
The correct, reliable implementation is two-fold:

1. In Global Instructions: The new, lean copilot-instructions.md file should include a
   "Resources" section with a Markdown link: (./docs/DOCUMENTATION-GUIDE.md). This
   assists the AI in finding the file if it becomes relevant.5
2. In Specific Tasks: For a task that requires this document, the user should explicitly inject
   it into the prompt (or prompt file): "Here is the documentation to follow:
   #file:'docs/DOCUMENTATION-GUIDE.md'."
   This approach moves from an unreliable command (telling the AI to find and read a file) to
   reliable context (injecting the file's contents directly into the context window).
   Recommendations: A Template for the New, Modular
   copilot-instructions.md
   The following template serves as a "gold standard" for a new, lean copilot-instructions.md file.
   It is concise, adheres to all best practices identified in this report, and explicitly guides the AI
   to the new modular system (the prompt files and chat modes).
   GitHub Copilot Instructions
3. Role and Core Directives
   You are an expert full-stack developer and DevOps engineer, acting as a pair-programming
   partner. Your primary knowledge areas include data modeling (Redis, MongoDB, PostgreSQL),
   CI/CD (GitHub Actions), and test-driven development (TDD).
   Core Responsibilities
   ● Act as a partner: Help build clean, maintainable, and well-tested projects.
   ● Automate: Design and implement CI/CD workflows.
   ● Design Data: Create efficient, scalable database schemas.
   ● Write Clean Code: Produce self-explanatory code.
   ● Use Open Standards: Prefer open-source tools over proprietary frameworks.
4. Immutable Coding Rules
   ● CRITICAL: Comments in source code are only for planning (e.g., TODO, FIXME). NEVER
   use comments for general explanation. Code must be self-explanatory.
   ● Always use TDD principles for new features (Red-Green-Refactor).
   ● All database schemas must be normalized unless explicitly for a document store.
5. Project Tech Stack
   ● Frontend: React, TypeScript
   ● Backend: Node.js, Ruby on Rails
   ● Database: PostgreSQL, Redis
   ● Testing: Jest, RSpec
   ● DevOps: GitHub Actions
6. Key Resources & Documentation
   ● (docs/DOCUMENTATION-GUIDE.md)
   ● (.github/workflows/)
   ● (docs/db-schema.md)
7. Your Workflow
   ● When asked to perform a complex task, you should first analyze the context (using
   @workspace if necessary) and propose a plan.
   ● For specific, repeatable tasks like "plan a TDD feature" or "refactor a component," I will
   use a Prompt File (e.g., /tdd-plan). Follow the instructions in that prompt.
   ● For specialized tasks, I will switch to a Chat Mode (e.g., "DevOps Agent").
   Sources des citations
8. Why Long System Prompts Hurt Context Windows (and How to Fix It) - Medium,
   consulté le novembre 7, 2025,
   https://medium.com/data-science-co lective/why-long-system-prompts-hurt-co
   ntext-windows-and-how-to-fix-it-7a3696e1cdf9
9. Lost-in-the-Middle Effect | LLM Knowledge Base - Promptmetheus, consulté le
   novembre 7, 2025,
   https://promptmetheus.com/resources/ lm-knowledge-base/lost-in-the-middle-e
   f
   fect
10. Lost in the Middle: How Language Models Use Long Contexts - MIT Press Direct,
    consulté le novembre 7, 2025,
    https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00638/119630/Lost-in-the-Mi
    ddle-How-Language-Models-Use-Long
11. Why shorter prompts enhance LLM performance ? - Basalt, consulté le novembre
    7, 2025,
    https://www.getbasalt.ai/post/balancing-scale- lm-performance-shorter-prompt
    s
12. Guidance on efficient use of copilot-instructions.md : r/GithubCopilot - Reddit,
    consulté le novembre 7, 2025,
    https://www.reddit.com/r/GithubCopilot/comments/1lfz0wt/guidance_on_efficien
    t_use_of_copilotinstructionsmd/
13. The Impact of Prompt Bloat on LLM Output Quality - MLOps Community,
    consulté le novembre 7, 2025,
    https://mlops.community/the-impact-of-prompt-bloat-on- lm-output-quality/
14. Disadvantage of Long Prompt for LLM - PromptLayer Blog, consulté le novembre
    7, 2025, https://blog.promptlayer.com/disadvantage-of-long-prompt-for- lm/
15. New research shows SHOUTING can influence your prompting results :
    r/PromptEngineering - Reddit, consulté le novembre 7, 2025,
    https://www.reddit.com/r/PromptEngineering/comments/1jzuwr9/new_research_s
    hows_shouting_can_influence_your/
16. Trustworthy Generative AI — Best Practices | LivePerson Developer Center,
    consulté le novembre 7, 2025,
    https://developers.liveperson.com/trustworthy-generative-ai-prompt-library-bes
    t-practices.html
17. Do Capital Letters Realy Matter? A Curious Discovery in AI Prompting | by Mirko
    Siddi, consulté le novembre 7, 2025,
    https://medium.com/@mirko.siddi/do-capital-letters-rea ly-matter-a-curious-disc
    overy-in-ai-prompting-988eafad9135
18. GitHub's Copilot Code Review: Can AI Spot Security Flaws Before You Commit? -
    arXiv, consulté le novembre 7, 2025, https://arxiv.org/html/2509.13650v1
19. Gemini 2.5 has a mi lion token context window and I'm being truncated after a
    couple of thousand · Issue #11813 · microsoft/vscode-copilot-release - GitHub,
    consulté le novembre 7, 2025,
    https://github.com/microsoft/vscode-copilot-release/issues/11813
20. Copilot Chat now has a 64k context window with OpenAI GPT-4o - GitHub
    Changelog, consulté le novembre 7, 2025,
    https://github.blog/changelog/2024-12-06-copilot-chat-now-has-a-64k-context
    window-with-openai-gpt-4o/
21. Keep it short and sweet: a guide on the length of documents that you provide to
    Copilot, consulté le novembre 7, 2025,
    https://support.microsoft.com/en-au/topic/keep-it-short-and-sweet-a-guide-on
    the-length-of-documents-that-you-provide-to-copilot-66de2ffd-deb2-4f0c-89
    84-098316104389
22. Microsoft Copilot Context Window Token Limits and Memory - Data Studios,
    consulté le novembre 7, 2025,
    https://www.datastudios.org/post/microsoft-copilot-context-window-token-limit
    s-and-memory
23. Orchestrating Multi-Step LLM Chains: Best Practices for Complex Workflows -
    Deepchecks, consulté le novembre 7, 2025,
    https://www.deepchecks.com/orchestrating-multi-step- lm-chains-best-practice
    s/
24. How do you manage complex, deterministic workflows in AI agents? : r/AI_Agents - Reddit, consulté le novembre 7, 2025,
    https://www.reddit.com/r/AI_Agents/comments/1jz07bs/how_do_you_manage_co
    mplex_deterministic_workflows/
25. pipeline-approval · Actions · GitHub Marketplace, consulté le novembre 7, 2025,
    https://github.com/marketplace/actions/pipeline-approval
26. adding approval process in github action workflow and send notification mail to
    approver · community · Discussion #47511, consulté le novembre 7, 2025,
    https://github.com/orgs/community/discussions/47511
27. slack-approval · Actions · GitHub Marketplace, consulté le novembre 7, 2025,
    https://github.com/marketplace/actions/slack-approval
28. LangGraph: Building Inte ligent Multi-Agent Workflows with State Management -
    Medium, consulté le novembre 7, 2025,
    https://medium.com/@saimoguloju2/langgraph-building-inte ligent-multi-agent
    workflows-with-state-management-0427264b6318
29. Accelerate test-driven development with AI - GitHub, consulté le novembre 7,
    2025, https://github.com/readme/guides/github-copilot-automattic
30. GitHub for Beginners: Test-driven development (TDD) with GitHub Copilot,
    consulté le novembre 7, 2025,
    https://github.blog/ai-and-ml/github-copilot/github-for-beginners-test-driven-de
    velopment-tdd-with-github-copilot/
31. Best practices for using GitHub Copilot, consulté le novembre 7, 2025,
    https://docs.github.com/en/copilot/get-started/best-practices
32. From Manual to Automated: Best Practices for TDD with GitHub Copilot - Jiaming
    Shang, consulté le novembre 7, 2025,
    https://blog.shangjiaming.com/automated-tdd-with-github-copilot/
33. Adding repository custom instructions for GitHub Copilot, consulté le novembre
    7, 2025,
    https://docs.github.com/copilot/customizing-copilot/adding-custom-instructions
    for-github-copilot
34. Use custom instructions in VS Code, consulté le novembre 7, 2025,
    https://code.visualstudio.com/docs/copilot/customization/custom-instructions
35. Get started with GitHub Copilot in VS Code, consulté le novembre 7, 2025,
    https://code.visualstudio.com/docs/copilot/getting-started
36. 5 tips for writing better custom instructions for Copilot - The GitHub Blog,
    consulté le novembre 7, 2025,
    https://github.blog/ai-and-ml/github-copilot/5-tips-for-writing-better-custom-ins
    tructions-for-copilot/
37. Best practices for using GitHub Copilot to work on tasks - GitHub Enterprise
    Cloud Docs, consulté le novembre 7, 2025,
    https://docs.github.com/enterprise-cloud@latest/copilot/tutorials/coding-agent/g
    et-the-best-results
38. Use prompt files in VS Code, consulté le novembre 7, 2025,
    https://code.visualstudio.com/docs/copilot/customization/prompt-files
39. GitHub Copilot DevOps Excelence: Prompt Files vs Instructions vs Chat Modes,
    consulté le novembre 7, 2025,
    https://azurewithaj.com/posts/github-copilot-prompt-instructions-chatmodes/
40. How to Use Prompt Files in GitHub Copilot VS Code, consulté le novembre 7,
    2025, https://www.youtube.com/watch?v=nNiDplJqU6w
41. Difference between the chatmodes and agents folders : r/GithubCopilot - Reddit,
    consulté le novembre 7, 2025,
    https://www.reddit.com/r/GithubCopilot/comments/1onrioo/difference_between_
    the_chatmodes_and_agents/
42. Custom chat modes in VS Code, consulté le novembre 7, 2025,
    https://code.visualstudio.com/docs/copilot/customization/custom-chat-modes
43. Customize chat to your workflow - Visual Studio Code, consulté le novembre 7,
    2025, https://code.visualstudio.com/docs/copilot/customization/overview
44. How to Use GitHub Copilot Chat Modes in VS Code (MCP Management),
    consulté le novembre 7, 2025, https://www.youtube.com/watch?v=kw5GNtihCh0
45. Copilot ask, edit, and agent modes: What they do and when to use them - The
    GitHub Blog, consulté le novembre 7, 2025,
    https://github.blog/ai-and-ml/github-copilot/copilot-ask-edit-and-agent-modes
    what-they-do-and-when-to-use-them/
46. visual studio code - How to use GitHub Copilot for multiple files? - Stack
    Overflow, consulté le novembre 7, 2025,
    https://stackoverflow.com/questions/76509513/how-to-use-github-copilot-for-m
    ultiple-files
47. Make chat an expert in your workspace - Visual Studio Code, consulté le
    novembre 7, 2025,
    https://code.visualstudio.com/docs/copilot/reference/workspace-context
48. Manage context for AI - Visual Studio Code, consulté le novembre 7, 2025,
    https://code.visualstudio.com/docs/copilot/chat/copilot-chat-context
49. GitHub Copilot Chat cheat sheet, consulté le novembre 7, 2025,
    https://docs.github.com/en/copilot/reference/cheat-sheet
50. In Github Copilot Chat - How to include al opened files as a context reference ·
    community · Discussion #155219, consulté le novembre 7, 2025,
    https://github.com/orgs/community/discussions/155219
51. 10 unexpected ways to use GitHub Copilot, consulté le novembre 7, 2025,
    https://github.blog/developer-ski ls/programming-languages-and-frameworks/10-unexpected-ways-to-use-github-copilot/
