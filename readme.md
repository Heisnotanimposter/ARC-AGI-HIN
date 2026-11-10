# ARC-AGI Master Development Hub (2019–2026) 🏛️

<img width="1200" height="300" alt="ARC-AGI-Timeline" src="https://github.com/user-attachments/assets/5428536b-157f-400a-a749-b2a6c286b55d" />

A central repository documenting, evaluating, and developing solutions across the historical evolution of the **Abstraction and Reasoning Corpus (ARC)** from **ARC-AGI-1** to **ARC-AGI-3**.

---

## ⏳ The Evolution Timeline (2019–2026)

### 🚀 2019: The Conceptual Launch
* **Foundational Thesis**: François Chollet publishes his seminal paper, *"On the Measure of Intelligence"*, introducing the Abstraction and Reasoning Corpus (**ARC-AGI-1**) as an explicit benchmark for human-like general intelligence and sample-efficient skill acquisition.
* **Initial Results**: Traditional deep learning models achieve near 0% accuracy, demonstrating strong resistance to standard gradient descent and pattern-memorization techniques.

### 🧩 2020–2023: The Program Synthesis & DSL Era
* **2020 Kaggle Competition**: François Chollet hosts the first ARC Challenge on Kaggle. Solo developer **"icecuber"** wins with a **21%** success rate using hand-crafted Domain-Specific Languages (DSLs) and combinatorial search.
* **2022 ARCathon**: François Chollet and Lab42 host ARCathon 2022 (118 teams from 47 countries). **Michael Hodel** wins 1st place with one of the most expressive ARC DSLs to date, receiving his trophy at the Swiss Global AI Awards following Demis Hassabis's honoring in Davos.
* **2023 ARCathon**: 265+ teams from 65 countries participate. 1st place is shared between **Somayyeh Gholami & Mehran Kazeminia (Team SM)** and **Jack Cole (Team MindsAI)**, both reaching **30%** on the private evaluation set.
* **LLM Stagnation**: Large Language Models (LLMs) remain stuck below 5% accuracy without specialized inference search or domain tokenization.

### ⚡ 2024: Test-Time Compute & The LLM ARChitect Breakthrough
* **ARC Prize Launch**: Mike Knoop and François Chollet establish the ARC Prize Foundation with a \$1,000,000+ bounty to accelerate open-source AGI research.
* **Inference-Time Scaling**: Research pivots from parameter scaling to test-time adaptation (TTA) and inference compute.
* **Top Performers**:
  * **The LLM ARChitect (Team HINAGI / ARChitects)** achieves **53.5%** (56.5% post-deadline) on the private evaluation set via LoRA fine-tuned 8B models, reduced 64-token representations, Depth-First Search (DFS) candidate exploration, and multi-perspective AugScore candidate selection.
  * Systems powered by frontier LLMs generate and verify thousands of candidate programs against prompt examples.
* **OpenAI o3 Benchmark**: OpenAI's reasoning model `o3` achieves **87.5%** on the semi-private evaluation set using extreme test-time computation (172× baseline inference budget).

### 📈 2025: Scaling Granular Complexity (ARC-AGI-2)
* **ARC-AGI-2 Launch**: The ARC Prize Foundation releases ARC-AGI-2 as a non-profit initiative with a \$725,000+ prize pool to replace the original test set as frontier models approached human performance.
* **1,000+ Granular Tasks**: Introduces fine-grained, high-complexity tasks designed to prevent memorization and rigorously test abstract generalization.
* **Human vs. AI Gap**: Human subjects retain near ~100% scores, but AI model performance drops sharply from 50%+ on ARC-1 to 20–30% on ARC-2.
* **NVIDIA NVARC Victory**: Team NVARC takes 1st place with **24%** accuracy on the private test set, demonstrating that a **compact 4B parameter model** trained on millions of procedurally generated synthetic tasks outperforms brute-force 70B+ architectures.

### 🎮 2026: Interactive Agentic Reasoning (ARC-AGI-3)
* **ARC-AGI-3 Paradigm Shift**: The competition transitions from static, single-turn grid puzzles to an interactive, dynamic agent benchmark.
* **ARCEngine Dynamic Environments**: Introduces ~100 unseen game environments powered by the open-source **ARCEngine**. Agents receive no text instructions or explicit goal descriptions.
* **Relative Human Action Efficiency (RHAE)**: Official scoring evaluates both level completion and action parsimony relative to human medians:
  $$S_{l,e} = \min\left(115.0, \left(\frac{h_{l,e}}{a_{l,e}}\right)^2 \times 100\right)$$
* **HINAGI SOTA Agent**: Incorporates SGLang high-throughput speculative serving, Python sandbox mental planning (A*, BFS, Sokoban solvers), automated action guards (cycle detection, death-repeat blocker), and rigorous empirical validation.

---

## 📁 Repository Architecture

The repository is structured into dedicated competition and research directories:

```
ARC-AGI-HIN/
├── README.md                      # Unified Master Development Hub & Evolution Timeline
├── LICENSE                        # Repository license
│
├── HINAGI 2024/                   # 🏆 (2024) ARC-AGI-1 & The LLM ARChitect (53.5 LB)
│   ├── README.md                  # Comprehensive 2024 technical documentation & study guide
│   ├── arc-prize-2024-main/       # ARChitects winning Kaggle solution (LoRA + DFS + AugScore)
│   │   └── plain/
│   │       ├── training_code/     # Model fine-tuning, TTT, and evaluation scripts
│   │       └── kaggle_notebooks/  # Kaggle submission notebooks (53.5 pts)
│   ├── arc-prize-2024-local/      # Modular Vision Transformer (ViT) local pipeline
│   ├── arc-prize-2024-colab/      # Google Colab mirrored execution environment
│   ├── arc-prize-2024-colab2/     # Experimental architectures (STN, xLSTM, AE+CNN+LSTM)
│   └── sample/                    # Baseline solvers and diagnostic utilities
│
├── HINAGI 2025/                   # 📈 (2025) ARC-AGI-2 Granular Benchmark Hub
│   ├── README.md                  # ARC-AGI-2 methodologies, 4B synthetic training & TTA
│   ├── ARC AGI 2/
│   │   ├── arc2_reasoning/        # Batched DFS solver, D4 symmetry & AugScore verifiers
│   │   ├── LSTM/                  # Multi-Head Attention CNN-LSTM & autoencoder models
│   │   ├── RL/                    # Reinforcement learning prototypes (Stable-Baselines3)
│   │   └── RNN/                   # Recurrent sequence models
│   ├── Attention_multihead_CNLSTM.py # Standalone visual attention neural solver
│   └── papers/                    # Reference literature on Vision Transformers & reasoning
│
└── HINAGI 2026/                   # 🎮 (2026) ARC-AGI-3 Interactive Agent Track & Dual-Track Hub
    ├── README.md                  # SOTA dual-track strategy, official score history & metrics
    ├── arc3_agentic/              # Interactive agentic framework (mental simulator, guards)
    ├── configs/                   # Production runtime environments and model configs
    ├── scripts/                   # Verification test suites, forensic auditors & builders
    ├── reports/                   # Phase audit reports, ledger reconciliations & benchmarks
    ├── artifacts/                 # Verification ledgers, execution logs & calibration data
    └── Paper/                     # NeurIPS / Kaggle Paper Track submission suite
        ├── README.md              # Paper track guide ($450,000 prize pool, 6-point rubric)
        ├── submission/            # Standalone Kaggle writeup, LaTeX manuscripts & evidence ledgers
        └── references/            # Past winning paper benchmarks
```

---

## 🛠️ Sub-Project Quick Navigation

| Project Module | Competition Focus | Key Solvers & Technologies | Entry Point |
| :--- | :--- | :--- | :--- |
| **`HINAGI 2024`** | ARC Prize 2024 (ARC-1) | Mistral-NeMo-8B, LoRA, DFS Candidate Generation, AugScore | [`HINAGI 2024/README.md`](HINAGI%202024/README.md) |
| **`HINAGI 2025`** | ARC Prize 2025 (ARC-2) | 4B Compact Models, Synthetic Data Engine, Attention CNLSTM | [`HINAGI 2025/README.md`](HINAGI%202025/README.md) |
| **`HINAGI 2026`** | ARC Prize 2026 (ARC-3 & ARC-2) | ARCEngine Interactive Agents, Mental Simulation, SGLang Serving | [`HINAGI 2026/README.md`](HINAGI%202026/README.md) |

---

## 📜 Citations & References
* François Chollet. *"On the Measure of Intelligence"*, arXiv:1911.01547 (2019).
* Daniel Franzen et al. *"The LLM ARChitect: Solving ARC-AGI Is A Matter of Perspective"* (2024).
* ARC Prize Foundation. *"ARC-AGI-2 & ARC-AGI-3 Benchmark Protocols"* (2025–2026).
