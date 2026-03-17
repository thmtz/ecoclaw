# **Architectural Blueprint for Energy-Aware Agentic Systems on the NVIDIA GB10 Superchip**

## **Strategic Context and the Agentic Paradigm Shift**

The artificial intelligence landscape is undergoing a profound structural transition, moving rapidly from stateless, single-turn conversational interfaces toward persistent, autonomous, multi-agent orchestrations. These agentic frameworks fundamentally alter the computational and energetic demands placed upon hardware infrastructure. Because autonomous agents require continuous background processing, repetitive reasoning loops, iterative tool execution, and massive context retention, they generate an exponentially higher volume of tokens to achieve a single user objective compared to traditional applications. As the industry scales these systems, the aggregate power consumption of inference workloads has vastly eclipsed that of initial model training, elevating energy efficiency from a secondary operational metric to a primary architectural mandate.

Simultaneously, the locus of artificial intelligence deployment is expanding from centralized, multi-megawatt cloud facilities to localized, on-premises edge workstations. The introduction of the NVIDIA GB10 Grace Blackwell System-on-Chip (SoC)—powering desktop supercomputers such as the DGX Spark, Dell Pro Max, HP ZGX Nano, and Lenovo ThinkStation PGX—democratizes access to datacenter-class architectures. By bringing massive unified memory pools and advanced quantization formats directly to the developer's desk, the GB10 enables the local execution of frontier-class models containing hundreds of billions of parameters. However, this localized power introduces severe complexities regarding hardware telemetry, real-time energy observability, and secure agent orchestration.

This comprehensive analysis provides an exhaustive architectural blueprint for developing an energy-aware agentic application on the NVIDIA GB10 platform. Engineered specifically within the rigid constraints of a six-hour rapid-prototyping environment—such as the NVIDIA GTC 2026 Hack for Impact Eco Impact track—this report synthesizes hardware-level power telemetry mechanisms, model performance profiles, the OpenClaw orchestration ecosystem, and the integration of real-time energy observability application programming interfaces (APIs). The resulting framework yields a highly actionable, risk-mitigated implementation strategy designed to achieve localized, algorithmic sustainability.

## **Hardware Architecture: The NVIDIA GB10 Grace Blackwell SoC**

Engineering an application that dynamically optimizes the tokens-per-joule (tok/J) ratio requires a foundational understanding of the underlying physical and micro-architectural realities of the execution environment. The hardware dictates both the performance ceilings of the deployed neural networks and the telemetry pathways available for power observability.

### **Micro-Architecture and the NVLink-C2C Interconnect**

The NVIDIA GB10 is a highly integrated, multi-die System-on-Chip manufactured using a custom TSMC 3nm-class process with advanced 2.5D packaging.1 The architecture represents an extreme codesign approach, merging a high-performance central processing unit (CPU) with a Blackwell-generation graphics processing unit (GPU) to eliminate the traditional bottlenecks of discrete PCIe expansion cards.

The CPU complex, co-developed with MediaTek, implements the Arm v9.2 architecture. It features 20 power-efficient cores arranged in a big.LITTLE configuration, comprising ten high-performance Cortex-X925 cores and ten efficiency-optimized Cortex-A725 cores.2 This heterogeneous CPU architecture allows for granular power management during the lightweight orchestration tasks typical of agentic event loops.

The GPU complex is built upon the Blackwell microarchitecture, featuring 48 Streaming Multiprocessors (SMs), 6,144 CUDA cores, and 5th-generation Tensor Cores.2 This GPU is roughly equivalent in raw compute capability to a desktop RTX 5070, but it is uniquely optimized for sparse matrix multiplication and advanced quantization formats.3 The CPU and GPU dies are fused via the NVIDIA NVLink-C2C (Chip-to-Chip) interconnect, providing a coherent bidirectional bandwidth of 600 GB/s, which drastically reduces the latency penalty typically incurred when moving data between host memory and device memory.3

### **Unified Memory Dynamics and the Bandwidth Bottleneck**

The most defining characteristic of the GB10 SoC is its memory subsystem. Unlike discrete datacenter GPUs that rely on ultra-high-bandwidth High Bandwidth Memory (HBM), or traditional x86 workstations that segregate system DDR5 from GPU GDDR6, the GB10 utilizes a completely unified memory architecture. The SoC is provisioned with 128 GB of LPDDR5X memory, shared coherently between the Grace CPU and the Blackwell GPU across a 256-bit interface.2

This architectural choice presents a profound dichotomy for large language model (LLM) inference. The massive 128 GB capacity is highly advantageous, allowing developers to load immense models—such as those scaling up to 200 billion parameters—entirely into memory without relying on catastrophic disk swapping or multi-node clustering.7 It also permits the simultaneous residency of the base model, extensive vector databases for Retrieval-Augmented Generation (RAG), and the complex state engines required by autonomous agents.10

Conversely, the bandwidth of this LPDDR5X implementation is rated between 273 GB/s and 301 GB/s.2 In the context of LLM inference, the initial prefill stage (processing the user prompt) is compute-bound, heavily utilizing the GPU's Tensor Cores. However, the subsequent decode stage (autoregressively generating tokens one by one) is strictly memory-bandwidth bound. During generation, the entire model weight matrix must be transferred from memory to the compute units for every single token produced. At 273 GB/s, generating tokens from a dense model occupying 60 GB of memory will yield a theoretical maximum throughput of roughly four to five tokens per second, severely impacting real-time interactivity. Consequently, optimizing inference on the GB10 requires aggressive mitigation of this bandwidth constraint through specific model architectures and quantization techniques.

### **Power Provisioning and Idle Draw Optimization**

The thermal and electrical characteristics of the GB10 define the parameters for energy efficiency modeling. The Thermal Design Power (TDP) for the integrated SoC is rated at 140W.5 The host workstation, such as the DGX Spark or Dell Pro Max, utilizes a 240W to 280W external power supply, leaving approximately 100W provisioned for auxiliary system components, including the NVMe solid-state drives, the cooling apparatus, and the high-speed networking interfaces.8

Accurate energy measurement requires establishing a stable baseline. Early production models of the DGX Spark exhibited anomalously high idle power consumption, consistently drawing between 37W and 45W while completely inactive.12 Hardware analysts traced this inefficiency to the NVIDIA ConnectX-7 SmartNIC, a 200Gbps networking interface designed to cluster multiple GB10 units together via RDMA over Converged Ethernet (RoCE).11 The controller for this interface remained fully powered even when unplugged.

A critical firmware update deployed via the DGX Base OS resolved this anomaly by implementing active hot-plug detection for the ConnectX-7 interface. When the networking port is unpopulated, the system dynamically cuts power to the controller, reducing total system idle draw by up to 18W.12 For developers constructing energy-aware applications, it is vital to ensure the host system is running the latest DGX OS 7.4.0 (or equivalent OEM firmware) to establish a normalized idle floor of 22W to 25W.12 This stable baseline is imperative for accurately isolating and calculating the precise energetic delta incurred by the active inference workload.

## **Telemetry Constraints: The Breakdown of NVML**

The most significant technical risk in deploying an application requiring per-inference energy observability on the GB10 platform is the systemic failure of the NVIDIA Management Library (NVML). NVML is the foundational C-based application programming interface utilized by virtually all standard industry monitoring tools, including nvidia-smi, Kubernetes device plugins, PyTorch profilers, and third-party emission trackers.15

### **The Unified Architecture Anomaly**

NVML was historically engineered under the assumption of discrete PCIe graphics accelerators equipped with dedicated framebuffers, isolated power delivery networks, and independent clock domains. The GB10, however, functions as a System-on-Chip where the operating system enumerates the Blackwell GPU as a PCIe device, but physically, the GPU shares its power phases, thermal limits, and memory pool directly with the Arm CPU.17

This architectural convergence breaks the core assumptions of the NVML API. When standard software attempts to query the GB10, the library surfaces critical errors:

* Memory queries via nvmlDeviceGetMemoryInfo consistently return NVML\_ERROR\_NOT\_SUPPORTED or display "Memory-Usage: N/A" because there is no isolated GPU framebuffer to measure.14  
* Power limit queries via nvmlDeviceGetPowerManagementLimit return null or crash container initializations (such as specific NIM microservices) that strictly require power management capabilities to boot.19  
* Direct power consumption polling via nvmlDeviceGetPowerUsage exhibits severe instability. During active, high-load inference workloads, the API frequently reports a static, erroneous baseline of approximately 5W with 0% utilization, completely failing to capture the dynamic power spikes of the hardware.17

Consequently, integrating standard open-source telemetry tools that depend on NVML will result in catastrophic monitoring failures, rendering real-time tokens-per-joule optimization mathematically impossible.

### **Software Bridges and Native Telemetry Alternatives**

To circumvent the NVML breakdown, developers must utilize specialized software shims or access the hardware through native Arm Linux interfaces.

The open-source community has engineered a workaround known as the nvml-unified-shim. This tool functions as a drop-in replacement for the libnvidia-ml.so.1 binary.20 It intercepts standard NVML calls and redirects them, resolving unified memory queries by parsing the Linux /proc/meminfo tree and utilizing the CUDA Runtime API.20 While this shim brilliantly resolves fatal crashes—allowing orchestration engines and inference servers like MAX Engine or vLLM to successfully detect the GPU—it is not a viable solution for energy monitoring. Due to semantic complexities in translating unified metrics, the shim currently hardcodes GPU utilization reports to 0%, rendering it useless for dynamic power profiling.20

The only mathematically sound and highly accurate method for extracting real-time power telemetry on the GB10 is utilizing tegrastats.21 Because the GB10 shares its lineage with the Tegra line of embedded SoCs, it supports this native NVIDIA utility, which bypasses NVML entirely. tegrastats interfaces directly with the Linux kernel's hardware monitoring (hwmon) and thermal zones, reading low-level sensor data from /sys/devices/virtual/thermal/ and related system nodes.21

By executing tegrastats with a specified millisecond polling interval, developers can access a highly granular stream of hardware statistics.22 The output explicitly details total unified RAM usage, CPU load mapped across all 20 big.LITTLE cores, the operating frequency of the GPU (represented as GR3D\_FREQ), and most importantly, the precise milliwatt consumption of the specific power rails.21 Wrapping tegrastats in a lightweight Python daemon to parse the POM\_5V\_GPU and system power metrics provides the precise, real-time telemetry required to feed dynamic energy-aware optimization APIs.

### **Operating System Privileges and Containerization**

Accessing these low-level metrics requires an understanding of the operating environment. The GB10 workstations ship with NVIDIA DGX Base OS, a customized, enterprise-grade distribution built upon the Ubuntu 22.04 LTS (and transitioning to 24.04) foundation.25 The OS is hardened with specific kernel patches (Linux v5.15 or v6.14) to ensure seamless compatibility with GPU Direct Storage and the unified memory architecture.25

Unlike locked-down, managed cloud environments, developers utilizing the DGX Spark are granted comprehensive local access. The system relies on standard Linux user authentication with full sudo privileges, allowing for the direct installation of system daemons, modifying kernel parameters, and configuring networking.27 However, to preserve the integrity of the highly tuned host environment, NVIDIA mandates that all inference workloads, agentic runtimes, and application dependencies be deployed via containerization using Docker or Enroot.14 The pre-installed NVIDIA Container Toolkit ensures that the hardware accelerators are seamlessly passed through to the isolated environments.30 Therefore, the optimal deployment strategy involves running the inference engine and the agentic framework within separate Docker containers while executing the tegrastats telemetry daemon directly on the host OS to ensure unhindered access to the sysfs hardware sensors.

## **The Agentic Layer: OpenClaw Orchestration**

The transition from isolated LLM interactions to autonomous productivity requires a robust orchestration framework. OpenClaw has rapidly established itself as the preeminent open-source platform for developing self-hosted, self-evolving AI agents.31 Unlike traditional chatbot interfaces that wait passively for user prompts, OpenClaw operates as a persistent, background intelligence layer capable of proactive execution.

### **Architectural Foundations of OpenClaw**

OpenClaw is engineered primarily in TypeScript and Node.js. Its architecture discards the concept of a standalone script in favor of a continuous, long-lived process known as the Gateway, which typically binds to local port 18789\.33 The Gateway functions as the central control plane, orchestrating several critical subsystems to achieve autonomous behavior:

1. **Multi-Channel Adapters:** The system decouples the agent's logic from its interface. Through native adapters, OpenClaw can simultaneously ingest and normalize messages from diverse platforms including WhatsApp, Telegram, Slack, Discord, and standard webhooks, allowing the agent to interact within the user's existing communication ecosystem.33  
2. **Session and Queue Management:** The Gateway maintains rigorous state management across multi-turn, asynchronous conversations. It queues incoming events and serializes executions to prevent context collisions, ensuring that long-running tasks do not interfere with immediate user queries.33  
3. **The Agent Runtime and Context Assembly:** OpenClaw abandons hardcoded system prompts in favor of a "File-System-as-Context" paradigm.35 The agent's identity and operational logic are defined dynamically by reading markdown files within a designated workspace directory.  
   * SOUL.md dictates the agent's persona, ethical boundaries, and conversational tone.36  
   * AGENTS.md serves as the procedural operating manual, outlining standard operating procedures and multi-agent handoff protocols.36  
   * TOOLS.md provides explicit instructions and guardrails for invoking external integrations.36  
   * MEMORY.md and chronological log files serve as a durable, long-term memory store, allowing the agent to recall previous interactions and decisions across reboot cycles.38  
4. **Skills and Plugin Extensibility:** The true utility of OpenClaw is derived from its Skills ecosystem. Skills are modular, natural-language plugin packages—often consisting of a single SKILL.md file containing YAML frontmatter and shell commands—that teach the agent new capabilities.33 Through the community registry known as ClawHub, agents can autonomously discover, download, and execute new skills to solve novel problems.40

### **The Security Crisis and the NemoClaw Resolution**

The fundamental design philosophy of OpenClaw—granting an autonomous AI full access to the host's file system, execution environment, and network stack to maximize utility—creates an unprecedented security vulnerability.41 In standard configurations, OpenClaw agents execute tools directly on the host machine without sandboxing.43

This unchecked autonomy has led to severe supply chain attacks. Threat actors have uploaded malicious packages to ClawHub disguised as legitimate utilities, such as cryptocurrency trackers or system monitoring tools.44 When an unsuspecting agent downloads and processes the compromised SKILL.md file, embedded prompt injection techniques force the LLM to execute obfuscated shell commands.45 These commands have successfully deployed commodity malware, such as the Atomic macOS Stealer (AMOS), harvesting browser cookies, SSH keys, cloud provider credentials, and environment variables stored in plaintext, before exfiltrating the data via reverse shells.44 Cybersecurity analysts have labeled unmodified OpenClaw deployments as inherently dangerous for enterprise environments.41

To resolve this critical flaw, NVIDIA collaborated with the OpenClaw development team to engineer a secure, enterprise-grade deployment stack named NemoClaw, officially unveiled at GTC 2026\.46 NemoClaw transforms the vulnerable framework into a highly governed platform deployable via a single command.48

The cornerstone of NemoClaw is the integration of the NVIDIA OpenShell runtime. OpenShell functions as a rigid, process-level sandbox that completely isolates the OpenClaw agent from the underlying host operating system.48 Security administrators define strict, policy-based guardrails using declarative YAML configuration files.49 These policies govern precisely which directories the agent can read or write, strictly enforce network egress rules to prevent unauthorized data exfiltration, and restrict the invocation of arbitrary shell commands.49 By deploying NemoClaw on the DGX Spark, developers can harness the full autonomous power of the agentic framework while guaranteeing cryptographic and systemic security, perfectly fulfilling the enterprise-readiness requirements implicitly expected in a high-stakes hackathon environment.

### **Integrating OpenTelemetry for Energy Observability**

To successfully implement a tokens-per-joule optimization strategy, the orchestration layer must possess deep observability into its own execution metrics. OpenClaw facilitates this natively through its sophisticated diagnostics-otel plugin.51

When activated within the openclaw.json configuration file, the Gateway transforms into a fully compliant OpenTelemetry (OTel) exporter. It utilizes the OTLP/HTTP (protobuf) protocol to stream granular telemetry data structured according to the OpenTelemetry GenAI Semantic Conventions.52

This native integration eliminates the need to build fragile, custom wrappers around the LLM inference endpoints. The emitted telemetry includes critical metric counters and histograms:

* **openclaw.tokens:** A comprehensive counter detailing exact input (prefill), output (decode), and cached token volumes per request, tagged with attributes identifying the specific model and provider.52  
* **openclaw.run.duration\_ms:** A precise histogram measuring the total wall-clock time required for the inference engine to return the generated response.52  
* **openclaw.message.duration\_ms:** Tracks the total end-to-end latency of the user interaction, including tool execution and internal queue wait times.52

By directing this OTLP stream into a localized OpenTelemetry Collector deployed on the DGX Spark, developers can intercept the token generation metrics. Simultaneously, the collector can ingest the physical power data harvested by the tegrastats daemon. This centralized pipeline allows for the real-time calculation of energy efficiency (e.g., mWh per request, tok/J) and the subsequent forwarding of this enriched dataset to external state-optimization engines like the Neuralwatt API.

## **Model Ecosystem and Inference Performance Analysis**

The selection of the underlying large language model is the most consequential architectural decision in the development of an energy-aware agent. The chosen model must balance complex reasoning capabilities necessary for autonomous tool usage against the strict memory bandwidth constraints of the GB10 SoC.

### **The Superiority of Mixture-of-Experts and NVFP4 Quantization**

As previously established, the 273 GB/s memory bandwidth of the GB10 severely bottlenecks the token generation phase of dense neural networks.2 To achieve the token throughput required for interactive agentic workflows (typically demanding a minimum of 20 to 30 tokens per second), the architecture must minimize the volume of data transferred from LPDDR5X memory to the GPU Tensor Cores during each decoding step.

The optimal solution relies on two converging technologies: Mixture-of-Experts (MoE) architectures and NVFP4 precision.

1. **Mixture-of-Experts:** MoE models decouple the total parameter count from the active parameter count. While a model may possess 100 billion total parameters, a routing mechanism ensures that only a small fraction (e.g., 10 to 14 billion parameters) are activated for any given token.54 This drastically reduces the memory bandwidth requirement, allowing large, highly capable models to achieve inference speeds comparable to much smaller dense models.  
2. **NVFP4 Quantization:** The NVIDIA Blackwell GPU architecture introduces hardware acceleration for 4-bit floating-point (NVFP4) math.3 Quantizing model weights from standard 16-bit formats (FP16/BF16) down to NVFP4 reduces the physical memory footprint by up to 60%. Utilizing micro-tensor scaling, this aggressive compression maintains high algorithmic accuracy while quadrupling the effective memory bandwidth, resulting in massive throughput gains.3

### **Comparative Performance on the DGX Spark**

Extensive community benchmarking, validated by resources such as the Spark Arena leaderboard, reveals distinct performance profiles for the primary open-source models available for the GB10 platform.

| Model Designation | Architecture Profile | Quantization Precision | VRAM Footprint | Decode Throughput | Suitability for Agentic MVP |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **Nemotron 3 Nano (30B)** | MoE (3.6B Active) | NVFP4 | \~38 GB | 56.1 \- 65.0 tok/s | **Optimal.** Delivers exceptional reasoning speed with minimal power draw. The low VRAM footprint preserves 90 GB of system memory for the OpenClaw Gateway, OTel Collector, and vector databases.58 |
| **Qwen3-Next-80B** | MoE (Sparse) | FP8 | \~115 GB | 45.0 \- 50.0 tok/s | **High Performance, High Risk.** Outstanding coding and planning capabilities. However, consuming 115 GB of the 128 GB unified pool leaves dangerously little overhead for the OS and container orchestration, risking Out-Of-Memory (OOM) crashes during complex tasks.61 |
| **Nemotron 3 Super (120B)** | MoE (12B Active) | NVFP4 | \~69.5 GB | 16.6 \- 20.0 tok/s | **Specialized.** Features a massive 1-million-token context window ideal for deep document analysis. However, the throughput is too sluggish to support the rapid, iterative "thought loops" required by a real-time routing agent.63 |
| **Qwen3-32B** | Dense | FP16/BF16 | \~64 GB | 9.4 \- 12.0 tok/s | **Sub-optimal.** As a dense model, every parameter must be loaded per token, severely bottlenecking on the 273 GB/s memory interface. Unusable for responsive applications.6 |
| **Cosmos Reason1-7B** | Dense VLM | FP16 | \~24 GB | 15.0 \- 20.0 tok/s | **Niche.** A highly specialized Vision-Language Model trained for spatial understanding and robotics. Unnecessary unless the hackathon project specifically demands physical AI or video stream analysis.66 |

The comparative data dictates that the **NVIDIA Nemotron 3 Nano (30B A3B) in NVFP4** is the undisputed optimal foundation for the six-hour hackathon. It guarantees fluid interactivity and robust tool-calling capabilities while drastically minimizing the risk of system instability caused by memory exhaustion.

## **Competitive Landscape: The State of Energy Observability**

Constructing a compelling submission for the Eco Impact track necessitates demonstrating a clear differentiation from existing solutions in the open-source ecosystem. The current landscape of AI energy measurement tools is largely fragmented, characterized by legacy frameworks optimized for offline model training rather than real-time, dynamic inference routing.

1. **CodeCarbon and Carbontracker:** These established Python libraries estimate total carbon equivalents based on the carbon intensity of the local electrical grid.15 However, their methodology is deeply flawed for modern architectures. They rely strictly on polling Intel RAPL registers and the NVIDIA NVML API to calculate average wattage over time.15 Because NVML power queries fail or report zero utilization on the GB10's unified architecture, these tools break entirely on the DGX Spark.15 Furthermore, they are not "token-aware," meaning they cannot attribute specific energy costs to individual queries in a concurrent serving environment.  
2. **Zeus (ML.ENERGY):** An advanced framework designed for the meticulous profiling and optimization of deep learning workloads.69 While Zeus successfully supports a diverse array of hardware and provides highly accurate energy measurements, it is fundamentally an offline optimization engine. It is designed to run batch workloads, measure the results, and suggest optimal batch sizes or power limits for future deployments. It is not engineered to function as an inline, real-time middleware router.  
3. **TokenPowerBench:** A recently published, open-source benchmarking tool specifically designed to attribute energy consumption accurately across the distinct prefill and decode phases of LLM inference.71 While TokenPowerBench provides excellent granular analytics (e.g., calculating exact joules per token based on sequence length), it is a declarative benchmarking suite. It utilizes YAML configurations to execute static tests and is not capable of integrating into live application logic to inform an autonomous agent.72

### **The Strategic Differentiation of the Neuralwatt API**

The integration of the Neuralwatt API provides a decisive architectural advantage over the existing open-source landscape. While frameworks like Zeus and TokenPowerBench passively *observe* and report historical power consumption, Neuralwatt is engineered for active, dynamic optimization.

By applying Q-learning algorithms to optimize GPU power states continuously, Neuralwatt maximizes the token-per-joule efficiency of the underlying hardware in real-time. Crucially, exposing this data via a hosted API allows the OpenClaw agent to ingest energy efficiency as a functional, decision-making parameter. This elevates the application from a passive monitoring dashboard into an "Energy-Aware Router"—an intelligent system that actively minimizes its own carbon footprint by dynamically evaluating the energetic cost of every task before execution.

## **Implementation Blueprint: The "GreenClaw" Eco-Router**

Given the rigid six-hour constraint of the Hack for Impact event, the specific hardware idiosyncrasies of the DGX Spark, and the evaluation criteria of the Eco Impact track, the most compelling and achievable Minimum Viable Product (MVP) is an **Energy-Aware Agentic Router featuring a real-time Observability Receipt UI**.

This architecture utilizes NemoClaw to orchestrate a workflow where the agent receives a user prompt, estimates the computational complexity, queries the Neuralwatt API to determine the most energy-efficient execution path (routing locally to the GB10 via Nemotron 3 Nano, or offloading to a hyper-efficient cloud endpoint), executes the task, and returns the output alongside a highly detailed cryptographic "Energy Receipt."

The following phase-by-phase execution plan outlines a highly aggressive, risk-mitigated approach to building the MVP within the hackathon time limits.

### **Phase 1: Environment Hardening and Telemetry Bridging (Hours 0.0 \- 1.5)**

The immediate technical priority is circumventing the NVML unified memory failure to guarantee that the system can harvest accurate physical power telemetry.

1. **System Initialization:** Establish an SSH connection to the DGX Spark. Verify that the DGX Base OS is updated to version 7.4.0 (to ensure the ConnectX-7 idle power fix is active) and that the NVIDIA Container Toolkit is functioning correctly.25  
2. **Telemetry Daemon Deployment:** Abandon any reliance on nvidia-smi or NVML Python bindings for power monitoring to avoid the 5W/0% utilization bug.17  
   * Deploy a lightweight Python background script directly on the host OS.  
   * This script will execute the native command sudo tegrastats \--interval 250 to poll the hardware sensors four times a second.22  
   * The daemon will parse the raw stdout, extracting the POM\_5V\_GPU (GPU rail) and MCPU (CPU rail) milliwatt values, aggregating them to calculate the total active SoC power draw.21  
   * The parsed data is then formatted and pushed to an accessible local port (e.g., a simple Flask endpoint) for ingestion by the observability pipeline.

### **Phase 2: Inference Engine and Observability Pipeline (Hours 1.5 \- 3.0)**

Establish the execution backend and configure the OpenTelemetry data routing.

1. **Local Inference Deployment:** Pull the optimized vLLM container image compatible with the GB10 architecture.  
   * Load the **NVIDIA Nemotron 3 Nano (30B A3B) NVFP4** model into the inference server.  
   * *Critical Risk Mitigation:* Explicitly configure the vLLM launch parameter \--gpu-memory-utilization 0.70. Failing to lower this from the default 0.90 on a unified memory system will result in severe memory pressure, swapping, and potential container crashes during live demonstrations.64  
2. **OpenTelemetry Infrastructure:** Deploy a standard OpenTelemetry Collector instance via Docker.  
   * Configure the otel-config.yaml to accept incoming OTLP/HTTP traffic from the OpenClaw Gateway.  
   * Utilize the collector's attributes processor to dynamically inject hardware metadata (e.g., hardware.type: GB10, region: us-west) into the incoming spans.74  
   * Configure the exporter pipeline to simultaneously route the enriched traces to a local visualizer (like Jaeger or a Grafana dashboard) for debugging, and out to the external Neuralwatt API endpoint.

### **Phase 3: NemoClaw Orchestration and Custom Skill Integration (Hours 3.0 \- 4.5)**

Deploy the agentic framework and encode the core energy-aware routing intelligence.

1. **Secure Orchestration:** Execute the single-command NemoClaw installation to deploy the OpenClaw Gateway wrapped within the OpenShell sandbox.46 This satisfies the highest standards of enterprise deployment and directly targets the hackathon's "Best Use of OpenClaw" bonus prize by demonstrating secure, policy-governed execution.  
2. **Telemetry Activation:** Edit the \~/.openclaw/openclaw.json configuration file to activate the native telemetry exporter:  
   JSON  
   "diagnostics": {  
     "enabled": true,  
     "otel": {  
       "enabled": true,  
       "endpoint": "http://localhost:4318",  
       "protocol": "http/protobuf",  
       "serviceName": "greenclaw-eco-router",  
       "traces": true,  
       "metrics": true  
     }  
   }

   This configuration ensures that critical metrics, specifically openclaw.tokens and openclaw.run.duration\_ms, are automatically streamed to the OTel collector.52  
3. **The Energy-Aware Router Skill:** Define the agent's logic by constructing a custom tool utilizing the registerTool() function within the OpenClaw API.76  
   * The evaluate\_energy\_cost tool will intercept the user's prompt and evaluate its complexity.  
   * The tool queries the localized tegrastats daemon to determine the current hardware power baseline, and simultaneously queries the Neuralwatt API to retrieve the historical tok/J efficiency metrics for both the local Nemotron 3 Nano model and a designated cloud endpoint.  
   * Based on a programmed efficiency threshold, the tool returns a strict boolean decision, forcing the agent to route the inference request to the path representing the lowest total carbon impact.

### **Phase 4: The Energy Receipt UX and Presentation Polish (Hours 4.5 \- 6.0)**

The success of a hackathon project hinges heavily on the user experience and the clarity of the core value proposition. The system must render the invisible energetic cost of artificial intelligence highly visible to the end user.

1. **Workflow Finalization:** The agent executes the requested task (e.g., summarizing a document or generating code) based on the routing decision.  
2. **Receipt Generation:** Upon completion of the task, a secondary OpenClaw skill queries the local OTel Collector using the specific trace\_id of the current session. It retrieves the exact token count (prefill \+ decode) and correlates it against the active power draw recorded by the tegrastats daemon during that specific time window.  
3. **UI Output:** The agent delivers the final conversational response to the user, immediately followed by a structured, easy-to-read "Energy Receipt" formatted in standard Markdown:

| Diagnostic Metric | Recorded Measurement |
| :---- | :---- |
| **Execution Pathway** | Local Edge (Nemotron 3 Nano 30B / NVFP4) |
| **Prompt Complexity** | 850 Tokens (Prefill) / 412 Tokens (Decode) |
| **Total Compute Latency** | 2.15 Seconds |
| **Active GPU Power Draw** | 72 Watts (Peak Delta over Baseline) |
| **Total Energy Consumed** | 0.043 Watt-hours (Wh) |
| **Calculated Efficiency** | 29,348 Tokens per Joule (tok/J) |
| **Eco-Routing Impact** | *Saved 0.12 Wh compared to Cloud API baseline.* |

## **Conclusion**

The NVIDIA DGX Spark, driven by the GB10 Grace Blackwell Superchip, represents a massive leap forward in the decentralization of AI compute infrastructure. However, its innovative unified memory architecture fundamentally invalidates traditional NVML-based power profiling methodologies, demanding a pivot toward native hardware telemetry such as the tegrastats utility to ensure accurate energy measurement.

By strategically bypassing the memory bandwidth bottleneck through the deployment of sparse, Mixture-of-Experts architectures—specifically the NVIDIA Nemotron 3 Nano model utilizing NVFP4 precision—developers can achieve the high-speed token generation necessary for fluid interactivity. When this optimized local hardware stack is orchestrated by the secure, sandboxed NemoClaw framework, the resulting system is uniquely positioned to execute complex, autonomous tasks safely.

The proposed "GreenClaw" architecture successfully synthesizes these technologies. By bridging the gap between raw hardware sensors, OpenClaw's native OpenTelemetry integrations, and the dynamic optimization capabilities of the Neuralwatt API, the implementation transcends passive monitoring. It delivers an intelligent, energy-aware routing engine that actively minimizes its own carbon footprint while providing users with transparent, actionable visibility into the environmental cost of artificial intelligence, perfectly aligning with the strategic imperatives of the Eco Impact challenge.

#### **Works cited**

1. \[News\] NVIDIA's GB10 Superchip Powering Project DIGITS is Reportedly Built with TSMC's 3nm Node \- TrendForce, accessed March 17, 2026, [https://www.trendforce.com/news/2025/01/10/news-nvidias-gb10-superchip-in-project-digits-is-reportedly-built-with-tsmcs-3nm-node/](https://www.trendforce.com/news/2025/01/10/news-nvidias-gb10-superchip-in-project-digits-is-reportedly-built-with-tsmcs-3nm-node/)  
2. NVIDIA GB10 Specs \- GPU Database \- TechPowerUp, accessed March 17, 2026, [https://www.techpowerup.com/gpu-specs/gb10.c4342](https://www.techpowerup.com/gpu-specs/gb10.c4342)  
3. The Engine Behind AI Factories | NVIDIA Blackwell Architecture, accessed March 17, 2026, [https://www.nvidia.com/en-us/data-center/technologies/blackwell-architecture/](https://www.nvidia.com/en-us/data-center/technologies/blackwell-architecture/)  
4. Arm-powered NVIDIA DGX Spark Puts High-Performance AI in the Hands of Millions of Developers, accessed March 17, 2026, [https://newsroom.arm.com/blog/arm-nvidia-dgx-spark-high-performance-ai](https://newsroom.arm.com/blog/arm-nvidia-dgx-spark-high-performance-ai)  
5. NVIDIA DGX Spark Specs \- GPU Database \- TechPowerUp, accessed March 17, 2026, [https://www.techpowerup.com/gpu-specs/nvidia-dgx-spark.b13048](https://www.techpowerup.com/gpu-specs/nvidia-dgx-spark.b13048)  
6. NVIDIA DGX Spark (GB10) Performance test vs 5090: LLM, Image and Video generation, accessed March 17, 2026, [https://www.proxpc.com/blogs/nvidia-dgx-spark-gb10-performance-test-vs-5090-llm-image-and-video-generation](https://www.proxpc.com/blogs/nvidia-dgx-spark-gb10-performance-test-vs-5090-llm-image-and-video-generation)  
7. NVIDIA Puts Grace Blackwell on Every Desk and at Every AI Developer's Fingertips, accessed March 17, 2026, [https://nvidianews.nvidia.com/news/nvidia-puts-grace-blackwell-on-every-desk-and-at-every-ai-developers-fingertips](https://nvidianews.nvidia.com/news/nvidia-puts-grace-blackwell-on-every-desk-and-at-every-ai-developers-fingertips)  
8. Hardware Overview — DGX Spark User Guide, accessed March 17, 2026, [https://docs.nvidia.com/dgx/dgx-spark/hardware.html](https://docs.nvidia.com/dgx/dgx-spark/hardware.html)  
9. Personal AI Supercomputer Powered by Blackwell | NVIDIA DGX Spark, accessed March 17, 2026, [https://www.nvidia.com/en-us/products/workstations/dgx-spark/](https://www.nvidia.com/en-us/products/workstations/dgx-spark/)  
10. I Was Ready to Return My DGX Spark. Then NVIDIA's January Update Changed Everything. \- Medium, accessed March 17, 2026, [https://medium.com/data-science-collective/i-was-ready-to-return-my-dgx-spark-then-nvidias-january-update-changed-everything-e67699155a45](https://medium.com/data-science-collective/i-was-ready-to-return-my-dgx-spark-then-nvidias-january-update-changed-everything-e67699155a45)  
11. Dell's version of the DGX Spark fixes pain points \- Jeff Geerling, accessed March 17, 2026, [https://www.jeffgeerling.com/blog/2025/dells-version-dgx-spark-fixes-pain-points/](https://www.jeffgeerling.com/blog/2025/dells-version-dgx-spark-fixes-pain-points/)  
12. Nvidia DGX Spark update cuts idle power by 32% or more — hot-plug detection on ConnectX NIC makes for a more efficient AI workstation | Tom's Hardware, accessed March 17, 2026, [https://www.tomshardware.com/tech-industry/artificial-intelligence/nvidia-dgx-spark-update-cuts-idle-power-by-32-percent-or-more-hot-plug-detection-on-connectx-nic-makes-for-a-more-efficient-ai-workstation](https://www.tomshardware.com/tech-industry/artificial-intelligence/nvidia-dgx-spark-update-cuts-idle-power-by-32-percent-or-more-hot-plug-detection-on-connectx-nic-makes-for-a-more-efficient-ai-workstation)  
13. NVIDIA DGX Spark Review The GB10 Machine is so Freaking Cool \- ServeTheHome, accessed March 17, 2026, [https://www.servethehome.com/nvidia-dgx-spark-review-the-gb10-machine-is-so-freaking-cool/4/](https://www.servethehome.com/nvidia-dgx-spark-review-the-gb10-machine-is-so-freaking-cool/4/)  
14. DGX Spark User Guide \- NVIDIA Documentation, accessed March 17, 2026, [https://docs.nvidia.com/dgx/dgx-spark/dgx-spark.pdf](https://docs.nvidia.com/dgx/dgx-spark/dgx-spark.pdf)  
15. Carbontracker, accessed March 17, 2026, [https://docs.carbontracker.info/](https://docs.carbontracker.info/)  
16. NVIDIA Management Library (NVML), accessed March 17, 2026, [https://developer.nvidia.com/management-library-nvml](https://developer.nvidia.com/management-library-nvml)  
17. DGX Spark GB10 GPU is stuck at \~5W power and 0% utilization even after all NVIDIA firmware updates, accessed March 17, 2026, [https://forums.developer.nvidia.com/t/dgx-spark-gb10-gpu-is-stuck-at-5w-power-and-0-utilization-even-after-all-nvidia-firmware-updates/356426](https://forums.developer.nvidia.com/t/dgx-spark-gb10-gpu-is-stuck-at-5w-power-and-0-utilization-even-after-all-nvidia-firmware-updates/356426)  
18. \[Bug\] Device plugin panics on NVIDIA GB10 (DGX Spark) \- GetMemoryInfo returns "Not Supported" \#1511 \- GitHub, accessed March 17, 2026, [https://github.com/Project-HAMi/HAMi/issues/1511](https://github.com/Project-HAMi/HAMi/issues/1511)  
19. Boltz-2 Container DGX Deployment Issue \- NVIDIA Developer Forums, accessed March 17, 2026, [https://forums.developer.nvidia.com/t/boltz-2-container-dgx-deployment-issue/353775](https://forums.developer.nvidia.com/t/boltz-2-container-dgx-deployment-issue/353775)  
20. NVML Support for DGX Spark Grace Blackwell Unified Memory \- Community Solution, accessed March 17, 2026, [https://forums.developer.nvidia.com/t/nvml-support-for-dgx-spark-grace-blackwell-unified-memory-community-solution/358869](https://forums.developer.nvidia.com/t/nvml-support-for-dgx-spark-grace-blackwell-unified-memory-community-solution/358869)  
21. Tegrastats Utility — NVIDIA Jetson Linux Developer Guide, accessed March 17, 2026, [https://docs.nvidia.com/jetson/archives/r36.5/DeveloperGuide/AT/JetsonLinuxDevelopmentTools/TegrastatsUtility.html](https://docs.nvidia.com/jetson/archives/r36.5/DeveloperGuide/AT/JetsonLinuxDevelopmentTools/TegrastatsUtility.html)  
22. Tegrastats Utility — Jetson Linux  
    Developer Guide 34.1 documentation, accessed March 17, 2026, [https://docs.nvidia.com/jetson/archives/r34.1/DeveloperGuide/text/AT/JetsonLinuxDevelopmentTools/TegrastatsUtility.html](https://docs.nvidia.com/jetson/archives/r34.1/DeveloperGuide/text/AT/JetsonLinuxDevelopmentTools/TegrastatsUtility.html)  
23. How does tegrastats measures average power consumption? \- NVIDIA Developer Forums, accessed March 17, 2026, [https://forums.developer.nvidia.com/t/how-does-tegrastats-measures-average-power-consumption/128192](https://forums.developer.nvidia.com/t/how-does-tegrastats-measures-average-power-consumption/128192)  
24. Tegrastats shows some GPU power consumption even when nothing is running on it(CV does not) \- Jetson AGX Xavier \- NVIDIA Developer Forums, accessed March 17, 2026, [https://forums.developer.nvidia.com/t/tegrastats-shows-some-gpu-power-consumption-even-when-nothing-is-running-on-it-cv-does-not/75012](https://forums.developer.nvidia.com/t/tegrastats-shows-some-gpu-power-consumption-even-when-nothing-is-running-on-it-cv-does-not/75012)  
25. NVIDIA DGX OS 6 User Guide, accessed March 17, 2026, [https://docs.nvidia.com/dgx/dgx-os-6-user-guide/introduction.html](https://docs.nvidia.com/dgx/dgx-os-6-user-guide/introduction.html)  
26. NVIDIA DGX Station Development Guide \- Amazon AWS, accessed March 17, 2026, [https://cdck-file-uploads-global.s3.dualstack.us-west-2.amazonaws.com/nvidia/original/4X/8/9/c/89c812f579fbabdacce828e32f7f7c70b7d8dd26.pdf](https://cdck-file-uploads-global.s3.dualstack.us-west-2.amazonaws.com/nvidia/original/4X/8/9/c/89c812f579fbabdacce828e32f7f7c70b7d8dd26.pdf)  
27. Security questions \- DGX Spark / GB10 \- NVIDIA Developer Forums, accessed March 17, 2026, [https://forums.developer.nvidia.com/t/security-questions/354868](https://forums.developer.nvidia.com/t/security-questions/354868)  
28. System Configurations — NVIDIA DGX OS 6 User Guide, accessed March 17, 2026, [https://docs.nvidia.com/dgx/dgx-os-6-user-guide/system\_configurations.html](https://docs.nvidia.com/dgx/dgx-os-6-user-guide/system_configurations.html)  
29. Quick Start Guide: NVIDIA DGX Spark with Ultralytics YOLO26, accessed March 17, 2026, [https://docs.ultralytics.com/guides/nvidia-dgx-spark/](https://docs.ultralytics.com/guides/nvidia-dgx-spark/)  
30. DGX Spark (GB10, ARM64) – Embedding NIM llama-3.2-nv-embedqa-1b-v2:1.10.0 fails with cudaErrorSymbolNotFound (onnx runtime) \- NVIDIA Developer Forums, accessed March 17, 2026, [https://forums.developer.nvidia.com/t/dgx-spark-gb10-arm64-embedding-nim-llama-3-2-nv-embedqa-1b-v2-1-10-0-fails-with-cudaerrorsymbolnotfound-onnx-runtime/354998](https://forums.developer.nvidia.com/t/dgx-spark-gb10-arm64-embedding-nim-llama-3-2-nv-embedqa-1b-v2-1-10-0-fails-with-cudaerrorsymbolnotfound-onnx-runtime/354998)  
31. Nvidia Groq Integration Boosts Open Source OpenClaw And Agent-As-A-Service Vision, accessed March 17, 2026, [https://www.opensourceforu.com/2026/03/nvidia-groq-integration-boosts-open-source-openclaw-and-agent-as-a-service-vision/](https://www.opensourceforu.com/2026/03/nvidia-groq-integration-boosts-open-source-openclaw-and-agent-as-a-service-vision/)  
32. I built 4 OpenClaws in 4 hours \- here's the architecture and results : r/SideProject \- Reddit, accessed March 17, 2026, [https://www.reddit.com/r/SideProject/comments/1r2mbai/i\_built\_4\_openclaws\_in\_4\_hours\_heres\_the/](https://www.reddit.com/r/SideProject/comments/1r2mbai/i_built_4_openclaws_in_4_hours_heres_the/)  
33. OpenClaw (Formerly Clawdbot & Moltbot) Explained: A Complete Guide to the Autonomous AI Agent \- Milvus, accessed March 17, 2026, [https://milvus.io/blog/openclaw-formerly-clawdbot-moltbot-explained-a-complete-guide-to-the-autonomous-ai-agent.md](https://milvus.io/blog/openclaw-formerly-clawdbot-moltbot-explained-a-complete-guide-to-the-autonomous-ai-agent.md)  
34. OpenClaw — Personal AI Assistant \- GitHub, accessed March 17, 2026, [https://github.com/openclaw/openclaw](https://github.com/openclaw/openclaw)  
35. Always-On Autonomous AI Agents: Exploring the OpenClaw Abstraction \[DLIT82488\], accessed March 17, 2026, [https://www.nvidia.com/gtc/session-catalog/sessions/gtc26-dlit82488/](https://www.nvidia.com/gtc/session-catalog/sessions/gtc26-dlit82488/)  
36. AI Agents 003 — OpenClaw Workspace Files Explained: SOUL.md, AGENTS.md, HEARTBEAT.md and More | by Roberto Capodieci | Mar, 2026, accessed March 17, 2026, [https://capodieci.medium.com/ai-agents-003-openclaw-workspace-files-explained-soul-md-agents-md-heartbeat-md-and-more-5bdfbee4827a](https://capodieci.medium.com/ai-agents-003-openclaw-workspace-files-explained-soul-md-agents-md-heartbeat-md-and-more-5bdfbee4827a)  
37. Agent Runtime \- OpenClaw, accessed March 17, 2026, [https://docs.openclaw.ai/concepts/agent](https://docs.openclaw.ai/concepts/agent)  
38. OpenClaw Won't Bite, A Zero-to-Hero Guide for People Who Hate Terminal \- Towards AI, accessed March 17, 2026, [https://pub.towardsai.net/openclaw-wont-bite-a-zero-to-hero-guide-for-people-who-hate-terminal-14dd1ae6d1c2](https://pub.towardsai.net/openclaw-wont-bite-a-zero-to-hero-guide-for-people-who-hate-terminal-14dd1ae6d1c2)  
39. SHIELD.md: A Security Standard for OpenClaw and AI Agents | by Thomas Roccia, accessed March 17, 2026, [https://blog.securitybreak.io/shield-md-a-security-standard-for-openclaw-and-ai-agents-b38637031460](https://blog.securitybreak.io/shield-md-a-security-standard-for-openclaw-and-ai-agents-b38637031460)  
40. OpenClaw Skills Development Guide for Developers (2026 Edition) \- GrowExx, accessed March 17, 2026, [https://www.growexx.com/blog/openclaw-skills-development-guide-for-developers/](https://www.growexx.com/blog/openclaw-skills-development-guide-for-developers/)  
41. Nvidia Says OpenClaw Is To Agentic AI What GPT Was To Chattybots, accessed March 17, 2026, [https://www.nextplatform.com/ai/2026/03/17/nvidia-says-openclaw-is-to-agentic-ai-what-gpt-was-to-chattybots/5209428](https://www.nextplatform.com/ai/2026/03/17/nvidia-says-openclaw-is-to-agentic-ai-what-gpt-was-to-chattybots/5209428)  
42. OpenClaw: Agentic AI in the wild — Architecture, adoption and emerging security risks, accessed March 17, 2026, [https://www.acronis.com/en/tru/posts/openclaw-agentic-ai-in-the-wild-architecture-adoption-and-emerging-security-risks/](https://www.acronis.com/en/tru/posts/openclaw-agentic-ai-in-the-wild-architecture-adoption-and-emerging-security-risks/)  
43. From SKILL.md to Shell Access in Three Lines of Markdown: Threat Modeling Agent Skills, accessed March 17, 2026, [https://snyk.io/articles/skill-md-shell-access/](https://snyk.io/articles/skill-md-shell-access/)  
44. Malicious OpenClaw Skills Used to Distribute Atomic MacOS Stealer | Trend Micro (US), accessed March 17, 2026, [https://www.trendmicro.com/en\_us/research/26/b/openclaw-skills-used-to-distribute-atomic-macos-stealer.html](https://www.trendmicro.com/en_us/research/26/b/openclaw-skills-used-to-distribute-atomic-macos-stealer.html)  
45. Malicious OpenClaw Skills Exposed: A Full Teardown \- Repello AI, accessed March 17, 2026, [https://repello.ai/blog/malicious-openclaw-skills-exposed-a-full-teardown](https://repello.ai/blog/malicious-openclaw-skills-exposed-a-full-teardown)  
46. NVIDIA Corporation \- NVIDIA Announces NemoClaw for the OpenClaw Community, accessed March 17, 2026, [https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-NemoClaw-for-the-OpenClaw-Community/default.aspx](https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-NemoClaw-for-the-OpenClaw-Community/default.aspx)  
47. Nvidia bets on OpenClaw, but adds a security layer \- how NemoClaw works, accessed March 17, 2026, [https://www.zdnet.com/article/nvidia-openclaw-nemoclaw-security-stack-gtc-2026/](https://www.zdnet.com/article/nvidia-openclaw-nemoclaw-security-stack-gtc-2026/)  
48. Run Autonomous, Self-Evolving Agents More Safely with NVIDIA OpenShell, accessed March 17, 2026, [https://developer.nvidia.com/blog/run-autonomous-self-evolving-agents-more-safely-with-nvidia-openshell/](https://developer.nvidia.com/blog/run-autonomous-self-evolving-agents-more-safely-with-nvidia-openshell/)  
49. Nvidia turns OpenClaw into an enterprise platform with NemoClaw, accessed March 17, 2026, [https://thenextweb.com/news/nvidia-nemoclaw-openclaw-enterprise-security](https://thenextweb.com/news/nvidia-nemoclaw-openclaw-enterprise-security)  
50. Policy YAML Examples | Self-hosted \- NVIDIA Run:ai Documentation, accessed March 17, 2026, [https://run-ai-docs.nvidia.com/self-hosted/platform-management/policies/policy-yaml-examples](https://run-ai-docs.nvidia.com/self-hosted/platform-management/policies/policy-yaml-examples)  
51. Instrumenting Your OpenClaw Agent with LangWatch via OpenTelemetry, accessed March 17, 2026, [https://langwatch.ai/blog/instrumenting-your-openclaw-agent-with-opentelemetry](https://langwatch.ai/blog/instrumenting-your-openclaw-agent-with-opentelemetry)  
52. Logging \- OpenClaw, accessed March 17, 2026, [https://docs.openclaw.ai/logging](https://docs.openclaw.ai/logging)  
53. Why 273 GB/s? Less Is More, Until It Isn't \- DGX Spark / GB10 \- NVIDIA Developer Forums, accessed March 17, 2026, [https://forums.developer.nvidia.com/t/why-273-gb-s-less-is-more-until-it-isn-t/359555](https://forums.developer.nvidia.com/t/why-273-gb-s-less-is-more-until-it-isn-t/359555)  
54. Running Nemotron 3 super on nvidia DGX Spark \- Kubesimplify, accessed March 17, 2026, [https://blog.kubesimplify.com/nemotron3-on-dgx-spark](https://blog.kubesimplify.com/nemotron3-on-dgx-spark)  
55. NVIDIA Blackwell Enables 3x Faster Training and Nearly 2x Training Performance Per Dollar than Previous-Gen Architecture, accessed March 17, 2026, [https://developer.nvidia.com/blog/nvidia-blackwell-enables-3x-faster-training-and-nearly-2x-training-performance-per-dollar-than-previous-gen-architecture/](https://developer.nvidia.com/blog/nvidia-blackwell-enables-3x-faster-training-and-nearly-2x-training-performance-per-dollar-than-previous-gen-architecture/)  
56. NVIDIA DGX Spark \- PNY.com, accessed March 17, 2026, [https://www.pny.com/en-eu/file%20library/professional/datasheet/dgx/pny-nvidia-dgx-spark-workstation-datasheet.pdf](https://www.pny.com/en-eu/file%20library/professional/datasheet/dgx/pny-nvidia-dgx-spark-workstation-datasheet.pdf)  
57. Open Source AI Tool Upgrades Speed Up LLM and Diffusion Models on NVIDIA RTX PCs, accessed March 17, 2026, [https://developer.nvidia.com/blog/open-source-ai-tool-upgrades-speed-up-llm-and-diffusion-models-on-nvidia-rtx-pcs/](https://developer.nvidia.com/blog/open-source-ai-tool-upgrades-speed-up-llm-and-diffusion-models-on-nvidia-rtx-pcs/)  
58. The state of Open-weights LLMs performance on NVIDIA DGX Spark : r/LocalLLaMA \- Reddit, accessed March 17, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1rhbtnw/the\_state\_of\_openweights\_llms\_performance\_on/](https://www.reddit.com/r/LocalLLaMA/comments/1rhbtnw/the_state_of_openweights_llms_performance_on/)  
59. NVIDIA Nemotron 3 Family of Models, accessed March 17, 2026, [https://research.nvidia.com/labs/nemotron/Nemotron-3/](https://research.nvidia.com/labs/nemotron/Nemotron-3/)  
60. Nemotron-3-Nano with llama.cpp | DGX Spark \- Nvidia, accessed March 17, 2026, [https://build.nvidia.com/spark/nemotron](https://build.nvidia.com/spark/nemotron)  
61. Building Local \+ Hybrid LLMs on DGX Spark That Outperform Top Cloud Models, accessed March 17, 2026, [https://forums.developer.nvidia.com/t/building-local-hybrid-llms-on-dgx-spark-that-outperform-top-cloud-models/359569](https://forums.developer.nvidia.com/t/building-local-hybrid-llms-on-dgx-spark-that-outperform-top-cloud-models/359569)  
62. DGX Spark \+ Qwen3-Next-80B: Proven Performance, But Missing Clear Path to NIM, TensorRT-LLM & Web UIs, accessed March 17, 2026, [https://forums.developer.nvidia.com/t/dgx-spark-qwen3-next-80b-proven-performance-but-missing-clear-path-to-nim-tensorrt-llm-web-uis/357820](https://forums.developer.nvidia.com/t/dgx-spark-qwen3-next-80b-proven-performance-but-missing-clear-path-to-nim-tensorrt-llm-web-uis/357820)  
63. New NVIDIA Nemotron 3 Super Delivers 5x Higher Throughput for Agentic AI, accessed March 17, 2026, [https://blogs.nvidia.com/blog/nemotron-3-super-agentic-ai/](https://blogs.nvidia.com/blog/nemotron-3-super-agentic-ai/)  
64. NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4 \- DGX Spark / GB10, accessed March 17, 2026, [https://forums.developer.nvidia.com/t/nvidia-nemotron-3-super-120b-a12b-nvfp4/363175](https://forums.developer.nvidia.com/t/nvidia-nemotron-3-super-120b-a12b-nvfp4/363175)  
65. DGX Spark performance \- NVIDIA Developer Forums, accessed March 17, 2026, [https://forums.developer.nvidia.com/t/dgx-spark-performance/356716](https://forums.developer.nvidia.com/t/dgx-spark-performance/356716)  
66. nvidia/Cosmos-Reason1-7B \- Hugging Face, accessed March 17, 2026, [https://huggingface.co/nvidia/Cosmos-Reason1-7B](https://huggingface.co/nvidia/Cosmos-Reason1-7B)  
67. NVIDIA Cosmos Reason 2 Brings Advanced Reasoning To Physical AI \- Hugging Face, accessed March 17, 2026, [https://huggingface.co/blog/nvidia/nvidia-cosmos-reason-2-brings-advanced-reasoning](https://huggingface.co/blog/nvidia/nvidia-cosmos-reason-2-brings-advanced-reasoning)  
68. sohampoddar26/LLM-energy-benchmark: Codes from the paper "Towards Sustainable NLP \- GitHub, accessed March 17, 2026, [https://github.com/sohampoddar26/LLM-energy-benchmark](https://github.com/sohampoddar26/LLM-energy-benchmark)  
69. Zeus Project \- The ML.ENERGY Initiative, accessed March 17, 2026, [https://ml.energy/zeus/](https://ml.energy/zeus/)  
70. GitHub \- ml-energy/zeus: Measure and optimize the energy consumption of your AI applications\!, accessed March 17, 2026, [https://github.com/ml-energy/zeus](https://github.com/ml-energy/zeus)  
71. Tokenpowerbench Achieves LLM Inference Power Consumption Analysis, Attributing Over 90% Of Energy To Prefill And Decode Stages \- Quantum Zeitgeist, accessed March 17, 2026, [https://quantumzeitgeist.com/90-percent-analysis-tokenpowerbench-achieves-llm-inference-power-consumption-attributing-energy/](https://quantumzeitgeist.com/90-percent-analysis-tokenpowerbench-achieves-llm-inference-power-consumption-attributing-energy/)  
72. TokenPowerBench: Benchmarking the Power Consumption of LLM Inference \- arXiv, accessed March 17, 2026, [https://arxiv.org/html/2512.03024v1](https://arxiv.org/html/2512.03024v1)  
73. Testing Nemotron 3 Nano Models on Nvidia DGX Spark/Jetson Thor with vLLM and FlashInfer, accessed March 17, 2026, [https://forums.developer.nvidia.com/t/testing-nemotron-3-nano-models-on-nvidia-dgx-spark-jetson-thor-with-vllm-and-flashinfer/360642](https://forums.developer.nvidia.com/t/testing-nemotron-3-nano-models-on-nvidia-dgx-spark-jetson-thor-with-vllm-and-flashinfer/360642)  
74. Mastering the OpenTelemetry Attributes Processor \- Dash0, accessed March 17, 2026, [https://www.dash0.com/guides/opentelemetry-attributes-processor](https://www.dash0.com/guides/opentelemetry-attributes-processor)  
75. How to add custom attributes to http auto instrumentation? · open-telemetry opentelemetry-js · Discussion \#4088 \- GitHub, accessed March 17, 2026, [https://github.com/open-telemetry/opentelemetry-js/discussions/4088](https://github.com/open-telemetry/opentelemetry-js/discussions/4088)  
76. Building Production-Ready Gemini CLI Extensions: The 15-Minute Gemini CLI Extension Guide for Engineers Who Don't Have 3 Hours to Debug \- Reza Rezvani, accessed March 17, 2026, [https://alirezarezvani.medium.com/building-production-ready-gemini-cli-extensions-the-15-minute-gemini-cli-extension-guide-for-408cb97f4c4a](https://alirezarezvani.medium.com/building-production-ready-gemini-cli-extensions-the-15-minute-gemini-cli-extension-guide-for-408cb97f4c4a)  
77. Swarm-coding: agentic development with multiple background agents \- The Craft \- Faire, accessed March 17, 2026, [https://craft.faire.com/swarm-coding-agentic-development-with-multiple-background-agents-3549adc7460d](https://craft.faire.com/swarm-coding-agentic-development-with-multiple-background-agents-3549adc7460d)