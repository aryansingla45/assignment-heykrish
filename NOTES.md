# NOTES

When building analytical pipelines like the Shelf Report, relying on Large Language Models (LLMs) requires understanding exactly where they excel and where they inevitably fail. 

Here is a breakdown of why we chose a deterministic SQLite database over an AI-driven math engine, and how Context, Memory, and RAG fit into the picture.

---

### 1. Why AI gets math wrong
LLMs are probabilistic token-prediction engines, not calculators. If you give an LLM a list of 1,534 JSON objects and ask it to compute the average sugar content, it doesn't parse the JSON into memory and run a `sum() / count()` loop. Instead, it attempts to "predict" what the resulting number should look like based on linguistic patterns in its training data. 

**The result is hallucination.** It will guess a plausible-sounding number (like "25.5g") that is completely untraceable. Furthermore, LLMs struggle to natively identify complex logical boundaries—such as realizing that 613 of the JSON objects lack sugar data entirely, or that 5 of them are impossible outliers (>100g).

**Our Solution:** We use the AI purely for *translation*, not computation. In `src/chat.py`, we ask Gemini to translate English into a SQL query. We then execute that query deterministically against SQLite. This guarantees the math is always 100% accurate, perfectly reproducible, and mathematically sound.

---

### 2. Context vs. Memory vs. RAG

When people talk about giving AI "knowledge," they often confuse these three distinct concepts. Here is how they differ in the scope of a data pipeline:

#### Context (The Short-Term Workspace)
Context is the immediate prompt and system instruction given to the LLM during a single API call. It is highly transient. 
* **Example in our project:** In `src/system_prompt.txt`, we inject the exact SQL schema and rules (like "exclude sugars > 100") into the context window. 
* **Limitation:** The context window is completely wiped clean the moment the API call finishes.

#### Memory (The Session State)
Memory allows the AI to remember the flow of a specific conversation over time by re-injecting previous questions and answers into the prompt under the hood.
* **Example:** If Priya asks *"What is the top biscuit brand?"* and then asks *"How much sugar do they have?"*, memory allows the AI to resolve "they" to "Britannia".
* **Limitation:** Memory is tied to a specific chat session or thread. If you start a new session, the AI forgets everything. It does not learn globally.

#### RAG (Retrieval-Augmented Generation)
RAG is the process of retrieving external facts from a database (usually a vector database) and injecting them into the Context window right before asking the LLM to generate an answer.
* **Example:** If Priya asks a qualitative question like *"What are the common ingredients in Parle biscuits?"*, a RAG system would search a vector database of ingredient text, retrieve the top 5 matches, inject them into the prompt context, and ask the LLM to summarize them.
* **Limitation:** RAG is fantastic for unstructured text (like ingredient lists or reviews), but it is **terrible for precise analytics**. If you ask a RAG system for the total count of biscuits in India, it will only retrieve the top *K* most relevant biscuit documents (e.g., 10 documents) and summarize those 10. It cannot perform a full table scan `COUNT()`. 

### Conclusion
By understanding these boundaries, the Shelf Report was built using a hybrid architecture. We use **Context** to give the LLM the rules of the database, but we rely entirely on **Deterministic SQL Execution** to actually touch the data. This completely eliminates the risk of AI hallucinating Priya's metrics.
