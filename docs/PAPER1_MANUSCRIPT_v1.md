# E₀: Structural Interference in Discrete Transition Systems

**Thomas Wehner**

---

## Abstract

We introduce E₀, a formal framework for discrete transition systems that
derives complex path amplitudes from three structural primitives: difference,
resistance, and historization. Through a constructive chain — tension,
coherence, Helmholtz field decomposition, connection, and phase — we obtain
amplitudes $\Psi = \exp(-S + i\Theta)$ that exhibit constructive and
destructive interference without postulating quantum mechanics. Probability
is not assumed but emerges from interference: normalized intensities
$P(a) = I(a)/\sum I(a')$ form a distribution derived from structural
amplitudes, not from axiomatic measure theory. We prove a Holonomy Independence Theorem establishing that phase
differences between paths depend only on path-local quantities. A hybrid
controller uses this interference to escape structural traps undetectable by
greedy methods. Our central empirical finding, validated across 380 graph
topologies, is that the choice of *summation geometry* — which paths
contribute to the amplitude — dominates over the choice of decision rule:
switching geometry changes trap-escape success from 0% to 100%, while
switching from deterministic to stochastic selection changes it by at most
24 percentage points. We identify path-family count and phase opposition as
structural predictors for when interference-based routing provides advantage.
All claims are explicitly classified as derived, empirical, or heuristic.

---

## 1. Introduction

### 1.1 Problem Statement

Local greedy decision-making in discrete transition systems is vulnerable to
structural traps. A *structural trap* is a configuration where the locally
cheapest transition leads toward a suboptimal or dead-end region, while a more
expensive first step would lead to a globally better outcome. Such traps arise
in planning, workflow routing, state-machine control, and any domain where
a myopic evaluation function must select among multiple successors.

Existing solutions add complexity:
- **Look-ahead methods** (A*, beam search) require explicit heuristic
  functions and grow exponentially with depth.
- **Reinforcement learning** (Q-learning, policy gradient) requires reward
  signals, exploration budgets, and converges slowly.
- **Monte Carlo Tree Search** (MCTS, AlphaZero-style) requires a simulation
  model and statistical convergence.

None of these provides a *structural* account of why traps exist or when
they can be detected from the transition landscape itself.

### 1.2 Our Approach

We introduce E₀, a formal framework that derives complex path amplitudes
from three primitive quantities — structural difference ($\Delta$), resistance
($R$), and historization ($H$). The derivation chain is constructive:

$$\Delta \to R_0 \to H \to \delta_H \to R_{\text{eff}} \to S \to C \to v \to \Phi \to v_{\text{grad}} / v_{\text{rot}} \to \omega \to \Theta \to \Psi$$

The key insight is that the transition field $v$ admits a discrete Helmholtz
decomposition into gradient and rotational components. The rotational
component induces a *connection* $\omega$ and *path phase* $\Theta$, which
combine with path tension $S$ to form complex amplitudes
$\Psi = \exp(-S + i\Theta)$. When multiple paths contribute to a decision,
these amplitudes exhibit *constructive and destructive interference* — an
effect that exposes structural traps invisible to local cost minimization.

The mathematical structure is analogous to path integrals in physics, but
the analogy is *derivative*: E₀ derives the amplitude from graph-theoretic
primitives rather than postulating it from physical principles.

### 1.3 Contributions

This paper makes five contributions:

1. **A formal framework** deriving complex path amplitudes from structural
   primitives, culminating in a Holonomy Independence Theorem establishing
   that phase differences depend only on path-local quantities (§3).

2. **Four summation geometries** with formal definitions and empirical
   comparison, showing that goal-reaching geometry eliminates intensity
   inflation artifacts in trap domains (§4).

3. **A hybrid controller** that uses amplitude-based interference to override
   greedy decisions when structural traps are detected, with three operating
   modes (§5).

4. **The geometry-dominance result:** on trap-containing domains, the choice
   of summation geometry determines success or failure ($0\% \to 100\%$),
   while the choice of decision rule changes outcomes by at most 24
   percentage points (§6).

5. **A topology classification** across 380 directed graphs, identifying
   path-family count and phase opposition ($|\Delta\Theta| > \pi/2$) as
   structural predictors for when interference-based routing helps (§7).

### 1.4 Scope and Honesty

E₀ explicitly classifies every claim as *derived* (follows from the
structural chain), *empirical* (demonstrated through experiments), or
*heuristic* (works operationally but not yet derived). Table 1 in Appendix C
provides the full classification.

This paper does **not** claim:
- A continuous-limit formalization.
- Probabilistic convergence guarantees.
- Real-world deployment evidence.
- A complete physical theory.

It claims a formally explicit, reproducible, and honestly scoped framework
for structural interference in discrete transition systems.

---

## 2. Related Work

E₀ combines elements from several established research traditions. We
organize the related work along four axes — path aggregation, interference
dynamics, geometric graph structure, and adaptive planning — and then
position E₀ at their intersection.

### 2.1 Path-Integral and Inference-Based Control

The idea of weighting trajectories by exponentials of costs and summing
over path families originates in path-integral control theory. Kappen
[1] shows that for a class of stochastic control problems, the nonlinear
Hamilton–Jacobi–Bellman equation can be linearized via a log-transformation
of the cost-to-go, in explicit analogy to the Schrödinger equation. The
resulting solution is expressible as a path integral over trajectories
weighted by $\exp(-S)$. Theodorou et al. [2] operationalize this as PI²
(Policy Improvement with Path Integrals), a reinforcement learning algorithm
that scales to high-dimensional continuous systems.

For discrete settings, Todorov's Linearly-Solvable MDPs (LMDPs) [3] model
control as modification of transition distributions, with control cost
measured via KL divergence. An exponential transformation of the value
function yields a linear eigenvalue problem — a structure closely analogous
to E₀'s $\exp(-S)$ coherence. The Control-as-Inference framework
(Kappen et al. [4]) generalizes this, reformulating nonlinear stochastic
control as KL minimization, with path-integral control as a special case.
Levine [5] provides a unifying Maximum-Entropy RL perspective where optimal
control is recast as probabilistic inference over trajectories.

Related work on trajectory distributions includes Maximum-Entropy Inverse RL
(Ziebart et al. [6]), which defines globally normalized distributions over
decision sequences, and Soft Actor-Critic (Haarnoja et al. [7]), which
operationalizes maximum-entropy RL in deep off-policy settings.

**Distinction from E₀:** This entire tradition uses *real-valued, positive*
trajectory weights (Boltzmann/exponential). E₀ shares the exponential
weighting $\exp(-S)$ for magnitude but additionally derives a *phase*
$\Theta$ from the rotational component of the transition field, enabling
*destructive* interference — an effect absent in classical path-integral
control.

### 2.2 Quantum Walks and Interference on Graphs

Quantum walks provide the prototypical formalism for graph dynamics governed
by complex-amplitude interference rather than positive-weight diffusion.
Aharonov et al. [8] define quantum walks as unitary evolution on
Hilbert-space states indexed by graph vertices, showing that mixing-time
behavior differs qualitatively from classical random walks. Farhi and
Gutmann [9] demonstrate that interference allows certain tree structures to
be "penetrated" exponentially faster than by classical walks.

In the AI context, Projective Simulation (PS) by Briegel and De las
Cuevas [10] models deliberation as a random walk on an episodic memory
graph, with a natural quantization route via quantum walks. Formal analysis
shows convergence to optimal behavior in a large class of MDPs [11].
Flamini et al. [12] implement decision-making via single-photon quantum
walks, with interference as an explicit decision mechanism.

**Distinction from E₀:** Quantum walks postulate unitary evolution; E₀
*derives* the complex amplitude from structural primitives (§3). Quantum
walks operate on symmetric or undirected graphs with uniform coupling; E₀
operates on directed graphs with heterogeneous edge parameters ($\Delta$,
$R$). The interference effect in E₀ is structural, not quantum-mechanical.

### 2.3 Geometric Structure on Graphs: Connections, Holonomy, and Gauge Equivariance

E₀'s connection $\omega$ and holonomy (Defs. 14–16) have precedents in
differential geometry and its discrete adaptations.

**Continuous setting.** Berry [13] shows that adiabatic transport around a
closed cycle in parameter space acquires a geometric phase factor — a path
integral of the connection one-form, independent of traversal speed. Liu
et al. [14] formalize discrete connections and covariant derivatives on
meshes, defining holonomy as the rotation accumulated by parallel transport
along closed paths, expressible via Stokes' theorem as the integral of
curvature.

**Graph learning.** Singer and Wu [15] define Vector Diffusion Maps, where
edges carry orthogonal transformations and path consistency (agreement of
transport along different paths) serves as an affinity signal — directly
analogous to E₀'s holonomy-based phase differences. Favoni et al. [16]
construct lattice gauge equivariant CNNs where Wilson loops (holonomies)
are the gauge-invariant observables, with experiments on SU(2) gauge theory.
Cohen and Welling [17] extend equivariance from global symmetries to local
gauge transformations. He et al. [18] (Gauge Equivariant Transformer) embed
parallel transport into attention mechanisms. Gerken et al. [19] survey
geometric deep learning with gauge equivariance on fiber bundles.

Bodnar et al. [20] (Sheaf Neural Networks) generalize graph diffusion to
non-constant edge relations. Recent work on loop invariants in graph learning
(Chen et al. [21]) argues that specific holonomies carry learning-relevant
signal beyond what spectral methods capture, and that standard GNNs are
not invariant-faithful under gauge randomization.

**Distinction from E₀:** These works use geometric structures primarily for
*representation learning* (perception, classification). E₀ uses connection
and holonomy as *decision operators* — the phase $\Theta$ directly enters the
action-selection mechanism via interference. Furthermore, E₀ derives its
connection from the Helmholtz decomposition of the transition field (§3.5–3.6)
rather than postulating edge-parallel transporters.

### 2.4 Multi-Goal and Multi-Objective Planning

Cluster D of E₀'s design space — multi-goal amplitude aggregation (§4,
Def. 25) — intersects with established work on goal-conditioned and
multi-objective sequential decision-making.

Schaul et al. [22] (UVFA) introduce value functions $V(s, g; \theta)$ that
generalize over states *and* goals. Andrychowicz et al. [23] (HER) make
failed trajectories informative through goal relabeling. Roijers et al. [24]
survey multi-objective sequential decision-making, establishing when
scalarization is insufficient. Felten et al. [25] provide benchmarking
toolkits for MORL.

**Distinction from E₀:** Multi-goal RL conditions on goals via reward
shaping or relabeling. E₀'s goal-reaching geometry (Def. 25) structurally
restricts which paths contribute to the amplitude — a geometric filter
rather than a reward signal. The multi-goal effect in E₀ is that alternative
goal paths provide coherent intensity "rescue" for actions that suffer
destructive interference toward a single goal.

### 2.5 History-Dependent Costs and Adaptive Graph Planning

E₀'s historization (Defs. 4–6) — where realized transition outcomes modify
future edge resistances — connects to work on adaptive and history-dependent
graph planning.

Cowlagi and Tsiotras [26] present algorithms for shortest paths when
transition costs depend on prior path history, as a nontrivial modification
of Dijkstra's algorithm. Koenig and Likhachev [27] (D* Lite) address
incremental replanning under changing costs. Phillips et al. [28]
(Experience Graphs) learn from prior episodes to accelerate online planning.

In RL, Tennenholtz et al. [29] formalize Dynamic Contextual MDPs (DCMDPs)
for non-Markovian, history-dependent environments where long-term history
produces cumulative effects. Genewein et al. [30] show that memory-based
sequence models approximate Bayesian inference over latent switching points
in piecewise-stationary environments.

**Distinction from E₀:** Classical history-dependent costs modify scalar
edge weights. E₀'s historization modifies *resistance*, which propagates
through the full derivation chain to alter *phase structure* and
*interference patterns* — a qualitatively richer feedback mechanism.

### 2.6 Positioning of E₀

The surveyed traditions each provide one axis of E₀'s construction:

| Tradition | E₀ analog | Key difference |
|-----------|-----------|----------------|
| Path-integral control | $\exp(-S)$ weighting | E₀ adds phase $\Theta$ → destructive interference |
| Quantum walks | Amplitude interference | E₀ derives amplitude, not postulates unitarity |
| Gauge/connection geometry | $\omega$, holonomy | E₀ uses as decision operator, not representation |
| Multi-goal RL | Goal-reaching geometry | Geometric path filter, not reward conditioning |
| History-dependent planning | Historization $\delta_H$ | Modifies phase structure, not just costs |

**Table 4: Positioning of E₀ relative to related traditions**

E₀'s contribution is the *combination*: coherent path aggregation with
complex interference on directed graphs, using a derived (not postulated)
connection/holonomy structure, with multi-goal geometry and
historization-driven adaptation — in a single deterministic decision
framework. No prior work integrates all five axes.

---

## 3. The E₀ Framework: Primitives and Derived Quantities

This section develops the mathematical core of E₀. Starting from three
primitive quantities — structural difference, resistance, and historization —
we derive a chain of structural quantities culminating in complex path
amplitudes that exhibit interference. Every definition is constructive: it
specifies exactly how the quantity is computed from its predecessors.

### 3.1 States and Transitions

**Definition 1** (Transition Graph).
A *transition graph* is a pair $\mathcal{G} = (X, E)$ where $X$ is a finite
set of *states* and $E \subseteq X \times X$ is a set of *directed edges*.
An edge $(x, y) \in E$ represents an admissible transition from state $x$ to
state $y$.

We write $x \to y$ for $(x, y) \in E$ and $N^+(x) = \{y \in X : x \to y\}$
for the set of admissible successors of $x$.

**Convention** (Directedness). The relation $E$ is not assumed to be
symmetric: $x \to y$ does not imply $y \to x$. This directedness is
essential — E₀ models systems where accessibility between states is
inherently asymmetric.

### 3.2 Structural Difference

**Definition 2** (Structural Difference).
The *structural difference* is a function

$$\Delta : E \to \mathbb{R}_{\geq 0}$$

that assigns to each directed edge $e = (x, y)$ a non-negative real number
$\Delta(x, y)$ measuring the magnitude of structural difference associated
with the transition from $x$ to $y$.

**Convention K3** (Non-Existent Edge). For $(x, y) \notin E$, the structural
difference is *undefined* (not zero). This distinguishes "no transition
exists" from "a zero-difference transition exists."

**Properties:**
- $\Delta(x, y) \geq 0$ for all $(x, y) \in E$.
- $\Delta(x, y) = 0$ is admissible and signifies a zero-difference transition.
- $\Delta$ is defined only on existing directed edges; it is not extended to
  arbitrary pairs.

### 3.3 Resistance and Historization

**Definition 3** (Base Resistance).
The *base resistance* is a function

$$R_0 : E \to \mathbb{R}_{> 0}$$

that assigns to each directed edge a positive real number representing the
baseline resistance of the transition, independent of prior history.

**Definition 4** (Historization).
For each edge $e \in E$, define the *historization state* as a pair

$$H(e) = (U(e), F(e))$$

where $U(e) \geq 0$ is the accumulated *success trace* and $F(e) \geq 0$ is
the accumulated *failure trace*.

Historization evolves after each realized transition outcome. Given a decay
parameter $\rho \in (0, 1)$, the update rule is:

$$U_{t+1}(e) = \rho \cdot U_t(e) + \mathbb{1}_{\text{success}}(e, t)$$

$$F_{t+1}(e) = \rho \cdot F_t(e) + \mathbb{1}_{\text{failure}}(e, t)$$

where $\mathbb{1}_{\text{success}}(e, t)$ equals 1 if edge $e$ was traversed
successfully at time $t$ and 0 otherwise (analogously for failure). Initial
conditions are $U_0(e) = F_0(e) = 0$ for all edges.

**Remark.** The decay factor $\rho$ implements exponential forgetting: recent
outcomes dominate over distant history. For edges not traversed at time $t$,
the effective traces $U_t, F_t$ still decay via a lazy catch-up mechanism:
if edge $e$ was last updated at time $\tau$, then at time $t > \tau$, the
effective traces are $U_{\text{eff}} = U_\tau \cdot \rho^{t - \tau}$ and
$F_{\text{eff}} = F_\tau \cdot \rho^{t - \tau}$.

**Definition 5** (Historization Correction).
The *historization correction* is

$$\delta_H(e) = \text{clip}\bigl(\lambda_f \cdot F(e) - \lambda_s \cdot U(e),\; -\delta_{\max},\; +\delta_{\max}\bigr)$$

with learning rates $\lambda_s, \lambda_f \geq 0$ and clipping bound
$\delta_{\max} > 0$.

**Interpretation:**
- $\delta_H > 0$: failures dominate $\Rightarrow$ increased resistance (path avoidance).
- $\delta_H < 0$: successes dominate $\Rightarrow$ decreased resistance (path reinforcement).
- $\delta_H = 0$: balanced history.

**Definition 6** (Effective Resistance).
The *effective resistance* is

$$R_{\text{eff}}(e) = \max\bigl(R_0(e) + \delta_H(e),\; \epsilon\bigr)$$

where $\epsilon > 0$ is a structural floor preventing zero or negative
resistance. In our implementation, $\epsilon = 10^{-10}$.

### 3.4 Tension and Coherence

**Definition 7** (Edge Tension).
The *tension* of a directed edge $e = (x, y) \in E$ is

$$S(x \to y) = \Delta(x, y) \cdot R_{\text{eff}}(x \to y)$$

Tension is the fundamental dynamic quantity of E₀. It expresses not merely
difference, and not merely resistance, but the *integration burden* of
difference under resistance.

**Convention:** If $(x, y) \notin E$, then $S(x \to y) = \infty$.

**Definition 8** (Path and Path Tension).
A *path* is an ordered sequence $p = (x_0, x_1, \ldots, x_n)$ with each
consecutive pair $(x_i, x_{i+1}) \in E$. The *path tension* is additive:

$$S(p) = \sum_{i=0}^{n-1} S(x_i \to x_{i+1})$$

If any single edge has $S = \infty$, then $S(p) = \infty$ (the path is
inadmissible).

**Definition 9** (Path Coherence).
The *coherence* of a path $p$ is

$$C(p) = \exp(-S(p))$$

**Proposition 1** (Coherence Bounds).
*For any path $p$ with $S(p) \in [0, \infty)$:*
1. $C(p) \in (0, 1]$.
2. $C$ is strictly monotonically decreasing in $S$.
3. $C(p) = 1$ if and only if $S(p) = 0$ (zero-tension path).
4. $\lim_{S \to \infty} C(p) = 0$ (infinite tension yields zero coherence).

*Proof.* Immediate from $\exp(-\cdot)$ being a strictly decreasing bijection
$[0, \infty) \to (0, 1]$. $\square$

### 3.5 Local Potential and Field Decomposition

The transition field admits a discrete Helmholtz decomposition into a
gradient (conservative) and rotational (non-conservative) component.

**Definition 10** (Transition Field).
The *transition field* assigns to each directed edge $(x, y) \in E$ the value

$$v(x, y) = \Delta(x, y) \cdot \exp\bigl(-S(x, y)\bigr)$$

where $S(x,y) = \Delta(x,y) \cdot R_{\text{eff}}(x,y)$ is the edge tension
(Def. 7). For $(x, y) \notin E$, we set $v(x, y) = 0$.

**Remark.** The transition field is not a probability. It is a structural
measure of *transition openness* — the degree to which a transition is both
different ($\Delta > 0$) and easy ($S$ small).

**Definition 11** (Local Potential — Helmholtz).
Let $\mathbf{L} = \mathbf{D} - \mathbf{A}$ be the combinatorial graph
Laplacian of the undirected skeleton of $\mathcal{G}$, where $\mathbf{D}$ is
the degree matrix and $\mathbf{A}$ is the adjacency matrix. The *local
potential* $\Phi : X \to \mathbb{R}$ is the solution to

$$\mathbf{L} \cdot \mathbf{\Phi} = \text{div}(\mathbf{v})$$

where $\text{div}(\mathbf{v})(x) = \sum_{y} v(x, y) - \sum_{y} v(y, x)$
is the discrete divergence. The system is solved via least-squares with gauge
fixing $\Phi(x_0) = 0$ for a reference node $x_0$.

**Definition 12** (Gradient Component).
The *gradient component* of the transition field is

$$v_{\text{grad}}(x, y) = \Phi(x) - \Phi(y)$$

This component is conservative by construction: for any closed path $\gamma$,
$\sum_\gamma v_{\text{grad}}(e) = 0$.

**Definition 13** (Rotational Component).
The *rotational component* is the residual

$$v_{\text{rot}}(x, y) = v(x, y) - v_{\text{grad}}(x, y)$$

for $(x, y) \in E$, and undefined for $(x, y) \notin E$.

By construction, the Helmholtz decomposition yields orthogonality in the
edge inner product:

$$\langle v_{\text{grad}}, v_{\text{rot}} \rangle_E = 0$$

**Remark** (Symmetrization). The Laplacian $\mathbf{L}$ is formed from the
*undirected skeleton* of $\mathcal{G}$, obtained by treating each directed
edge $(x,y) \in E$ as an undirected edge $\{x,y\}$. This is a deliberate
design choice: the divergence $\text{div}(\mathbf{v})$ already encodes the
full directional information of the transition field (Def. 10), so the
potential $\Phi$ need only redistribute it over the node set. The undirected
Laplacian provides the minimal symmetric operator for this redistribution.
On strongly asymmetric graphs (where most edges are one-directional), the
rotational residual $v_{\text{rot}}$ absorbs all directional asymmetry,
preserving the decomposition's validity. An alternative formulation using
the directed Hodge Laplacian (Jiang et al., 2011) would yield a richer
decomposition at the cost of additional structure; we leave this extension
to future work.

### 3.6 Connection and Phase

The rotational component of the transition field induces a connection
on the transition graph — a structure that measures the non-conservative,
orientation-dependent character of the transition landscape.

**Definition 14** (Connection).
The *connection* is the antisymmetric function

$$\omega(x, y) = \frac{1}{2}\bigl(v_{\text{rot}}(x, y) - v_{\text{rot}}(y, x)\bigr)$$

with the convention that $v_{\text{rot}}(x, y) = 0$ whenever $(x, y) \notin E$.

**Property** (Antisymmetry). By construction, $\omega(x, y) = -\omega(y, x)$.

**Remark** (Gauge Freedom). The connection $\omega$ depends on the Helmholtz
decomposition, which in turn depends on the gauge-fixing choice
$\Phi(x_0) = 0$ (Def. 11). A different reference node $x_0'$ shifts $\Phi$
by a constant, leaving $v_{\text{grad}}(x,y) = \Phi(x) - \Phi(y)$ invariant.
Consequently, $v_{\text{rot}}$, $\omega$, and $\Theta$ are *gauge-invariant*
with respect to reference node choice. However, the antisymmetrization in
Def. 14 is itself a *structural convention*: it is the unique antisymmetric
extraction from $v_{\text{rot}}$, but alternative connection definitions
(e.g., based on a directed Hodge decomposition) could yield different phase
assignments. We therefore state: $\Theta$ is *derived up to the gauge class*
defined by the Helmholtz decomposition and the antisymmetric extraction.
This gauge freedom is analogous to the choice of gauge in fiber-bundle
theory, where observables (here: holonomy, interference) are
gauge-invariant even though the connection itself is not unique across
gauge classes.

**Definition 15** (Path Phase).
The *path phase* accumulated along a path $p = (x_0, x_1, \ldots, x_n)$ is

$$\Theta(p) = \sum_{i=0}^{n-1} \omega(x_i, x_{i+1})$$

**Definition 16** (Holonomy).
For a closed path $\gamma$ with $\gamma_0 = \gamma_n$, the *holonomy* is

$$\text{Hol}(\gamma) = \Theta(\gamma) = \sum_{\gamma} \omega(e)$$

**Interpretation:**
- $\text{Hol}(\gamma) = 0$: the cycle has integrable (conservative) structure.
- $\text{Hol}(\gamma) \neq 0$: the cycle exhibits non-integrable,
  path-dependent structure — distinct paths between the same endpoints
  accumulate different phases.

**Theorem 1** (Holonomy Independence).
*Let $p_1$ and $p_2$ be two directed paths from $x$ to $y$ in $\mathcal{G}$,
and let $\gamma = p_1 \circ p_2^{-1}$ be the closed path obtained by
traversing $p_1$ forward and $p_2$ backward. Then*

$$\Delta\Theta = \Theta(p_1) - \Theta(p_2) = \text{Hol}(\gamma)$$

*and this quantity depends only on the edges in $p_1$ and $p_2$, not on any
external graph structure.*

*Proof.* Expand the phase difference using the definitions:

$$\Delta\Theta = \sum_{e \in p_1} \omega(e) - \sum_{e \in p_2} \omega(e)$$

Since $\omega(x, y) = \frac{1}{2}(v_{\text{rot}}(x,y) - v_{\text{rot}}(y,x))$
and $v_{\text{rot}} = v - v_{\text{grad}}$, the gradient contributions cancel:

$$\sum_{e \in p_1} v_{\text{grad}}(e) = \Phi(x) - \Phi(y) = \sum_{e \in p_2} v_{\text{grad}}(e)$$

because $v_{\text{grad}}$ is conservative (telescoping sum). Therefore:

$$\Delta\Theta = \frac{1}{2}\sum_{e \in p_1} \bigl(v_{\text{rot}}(e) - v_{\text{rot}}(\bar{e})\bigr) - \frac{1}{2}\sum_{e \in p_2} \bigl(v_{\text{rot}}(e) - v_{\text{rot}}(\bar{e})\bigr)$$

where $\bar{e}$ denotes the reverse of edge $e$. Each term depends only on
edge-local quantities ($v$ values on $p_1$ and $p_2$ edges and their
reverses), not on any vertex potential or external graph structure. $\square$

**Remark** (Locality). Although the Helmholtz decomposition that produces
$v_{\text{rot}}$ depends on the global graph structure (the Laplacian
pseudoinverse), the phase *difference* $\Delta\Theta$ reduces to edge-local
evaluations once $v_{\text{rot}}$ is computed. The global computation is a
one-time preprocessing step; all interference-relevant quantities are then
path-local.

**Corollary.** The phase difference $\Delta\Theta$ between two paths sharing
endpoints can be computed directly from the transition field values along
those paths, without solving for the global potential $\Phi$.

### 3.7 Complex Path Amplitude

**Definition 17** (Path Amplitude).
The *complex path amplitude* for a path $p$ is

$$\Psi(p) = \exp(-S(p) + i\Theta(p)) = \exp(-S(p))\cdot\exp(i\Theta(p))$$

This is not a quantum postulate. It is a mathematically natural compact
representation that combines:
- *path coherence* $|\Psi(p)| = \exp(-S(p)) = C(p)$ as magnitude, and
- *accumulated phase* $\arg(\Psi(p)) = \Theta(p)$ as angle.

**Remark** (On Probability). The normalized intensity $P(a) = I(a)/\sum I(a')$
(Def. 20) is a well-defined probability distribution over actions. However,
this probability is not *assumed* — it *emerges* from the interference of
complex amplitudes. The distinction is structural: in classical decision
theory, probabilities are primitive inputs; in E₀, they are derived outputs
of the amplitude summation. This parallels the Born rule in quantum mechanics,
where probabilities emerge from squared amplitudes rather than being
postulated independently.

**Key properties:**
- $\Psi(p) = 0$ if $S(p) = \infty$ (inadmissible path).
- $|\Psi(p)| = 1$ if $S(p) = 0$ (zero-tension path).
- $\Psi(p) \in \mathbb{R}_{>0}$ if $\Theta(p) = 0$ (zero-phase path).

**Definition 18** (Endpoint Amplitude and Summation Geometry).
Given a state $x$, an admissible action $a \in N^+(x)$, a horizon $h \in
\mathbb{N}$, and a *summation geometry* $G$ (Definition 21, §4), the *endpoint
amplitude* is

$$\Psi_G(a; x, h) = \sum_{p \in \mathcal{P}_G(x, a, h)} \Psi(p)$$

where $\mathcal{P}_G(x, a, h)$ is the set of paths starting at $x$ with
first hop $a$, of length $\leq h$, selected according to geometry $G$.

**Definition 19** (Intensity).
The *intensity* of action $a$ is

$$I(a) = |\Psi_G(a; x, h)|^2$$

**Definition 20** (Normalized Intensity).
The *normalized intensity* (Born-like probability) is

$$P(a) = \frac{I(a)}{\sum_{a'} I(a')}$$

where the sum ranges over all admissible actions $a' \in N^+(x)$.

**Proposition 2** (Interference).
*The intensity $I(a)$ exhibits interference: in general,*

$$I(a) = \left|\sum_p \Psi(p)\right|^2 \neq \sum_p |\Psi(p)|^2$$

*The inequality is strict whenever two or more contributing paths have
distinct phases $\Theta(p_i) \neq \Theta(p_j)$.*

*Proof.* Let $\Psi(p_k) = r_k e^{i\theta_k}$ with $r_k = C(p_k)$. Then:

$$I(a) = \left|\sum_k r_k e^{i\theta_k}\right|^2 = \sum_k r_k^2 + 2\sum_{j<k} r_j r_k \cos(\theta_j - \theta_k)$$

The cross terms $2r_j r_k \cos(\theta_j - \theta_k)$ are the interference
terms. They vanish only when all phase differences are $\pm\pi/2$
(orthogonal) or when there is only one path. In particular:

- *Constructive interference*: $\cos(\theta_j - \theta_k) > 0$ increases $I$.
- *Destructive interference*: $\cos(\theta_j - \theta_k) < 0$ decreases $I$.

$\square$

**Proposition 3** (Zero-Holonomy Reduction).
*If $\text{Hol}(\gamma) = 0$ for every cycle $\gamma$ in $\mathcal{G}$
(integrable transition field), then all paths from $x$ to any given endpoint
$z$ accumulate the same phase. In this case, the interference terms are
maximally constructive and intensity reduces to the squared sum of
coherences:*

$$I(a) = \left(\sum_p C(p)\right)^2$$

*Proof.* If the holonomy vanishes on all cycles, Theorem 1 implies
$\Theta(p_1) = \Theta(p_2)$ for any two paths sharing endpoints. Setting
$\theta_k = \theta$ for all $k$ in the expansion from Proposition 2:

$$I(a) = \left|\sum_k r_k e^{i\theta}\right|^2 = \left|e^{i\theta}\right|^2 \left(\sum_k r_k\right)^2 = \left(\sum_k C(p_k)\right)^2$$

$\square$

**Remark.** Proposition 3 shows that non-trivial interference — the phenomenon
that makes E₀'s amplitude-based routing different from simple coherence
summation — requires non-zero holonomy. This connects the purely geometric
property of the transition field (its rotational component) to an
operationally observable decision-level effect.

---

### Derivation Chain Summary

The complete dependency chain of E₀ is:

$$\Delta \to R_0 \to H \to \delta_H \to R_{\text{eff}} \to S \to C \to v \to \Phi \to v_{\text{grad}} / v_{\text{rot}} \to \omega \to \Theta \to \Psi$$

Each arrow represents a constructive derivation step. No quantity in this
chain is postulated independently — each follows from its predecessors and
the graph structure $\mathcal{G}$.

**Table 2: Notation Summary**

| Symbol | Name | Domain | Definition |
|--------|------|--------|------------|
| $\mathcal{G} = (X, E)$ | Transition graph | — | Def. 1 |
| $\Delta(x,y)$ | Structural difference | $\mathbb{R}_{\geq 0}$ | Def. 2 |
| $R_0(e)$ | Base resistance | $\mathbb{R}_{> 0}$ | Def. 3 |
| $H(e) = (U, F)$ | Historization state | $\mathbb{R}_{\geq 0}^2$ | Def. 4 |
| $\delta_H(e)$ | Historization correction | $[-\delta_{\max}, \delta_{\max}]$ | Def. 5 |
| $R_{\text{eff}}(e)$ | Effective resistance | $[\epsilon, \infty)$ | Def. 6 |
| $S(e)$ | Edge tension | $[0, \infty]$ | Def. 7 |
| $S(p)$ | Path tension | $[0, \infty]$ | Def. 8 |
| $C(p)$ | Path coherence | $(0, 1]$ | Def. 9 |
| $v(x,y)$ | Transition field | $[0, \infty)$ | Def. 10 |
| $\Phi(x)$ | Local potential | $\mathbb{R}$ | Def. 11 |
| $v_{\text{grad}}(x,y)$ | Gradient component | $\mathbb{R}$ | Def. 12 |
| $v_{\text{rot}}(x,y)$ | Rotational component | $\mathbb{R}$ | Def. 13 |
| $\omega(x,y)$ | Connection | $\mathbb{R}$ (antisym.) | Def. 14 |
| $\Theta(p)$ | Path phase | $\mathbb{R}$ | Def. 15 |
| $\text{Hol}(\gamma)$ | Holonomy | $\mathbb{R}$ | Def. 16 |
| $\Psi(p)$ | Path amplitude | $\mathbb{C}$ | Def. 17 |
| $I(a)$ | Intensity | $\mathbb{R}_{\geq 0}$ | Def. 19 |
| $P(a)$ | Normalized intensity | $[0, 1]$ | Def. 20 |

---

## 4. Summation Geometries

The definition of endpoint amplitude (Def. 18) depends on the choice of
*summation geometry* $G$, which determines which paths contribute to the
amplitude sum. This section formalizes four geometries, demonstrates that this
choice has material impact on decision outcomes, and identifies conditions
under which specific geometries are structurally appropriate.

### 4.1 The Geometry Problem

**Definition 21** (Summation Geometry).
A *summation geometry* $G$ is a function that, given a starting state $x$, an
action $a \in N^+(x)$, a horizon $h$, and optionally a goal set
$\mathcal{T} \subseteq X$, produces a set of paths:

$$G(x, a, h, \mathcal{T}) = \mathcal{P}_G(x, a, h) \subseteq \{p : p_0 = x,\; p_1 = a,\; |p| \leq h+1\}$$

The choice of $G$ determines which structural information reaches the
amplitude computation. Different geometries include different paths,
producing different interference patterns and potentially different
action rankings.

### 4.2 Four Geometries

We define four summation geometries, ordered by increasing structural
selectivity:

**Definition 22** (Prefix Geometry $G_{\text{prefix}}$).
Include all admissible paths of length 1 to $h$ starting with action $a$.
No repeated-state restriction. All prefixes of longer paths are included.

**Definition 23** (Simple Geometry $G_{\text{simple}}$).
Include all *simple* paths (no repeated states) of length 1 to $h$ starting
with action $a$. This suppresses loop inflation — paths that revisit states
are excluded.

**Definition 24** (First-Arrival Geometry $G_{\text{first}}$).
Include all paths up to length $h$ that stop upon first reaching a goal
state $g \in \mathcal{T}$. Non-goal prefixes are included. Requires
$\mathcal{T} \neq \emptyset$.

**Definition 25** (Goal-Reaching Geometry $G_{\text{goal}}$).
Include *only* paths that terminate at a goal state $g \in \mathcal{T}$, of
length $\leq h$. Non-goal-terminating paths are excluded entirely. Requires
$\mathcal{T} \neq \emptyset$.

**Table 3: Geometry Properties**

| Geometry | Loops | Non-goal paths | Requires goals | Selectivity |
|----------|-------|---------------|----------------|-------------|
| Prefix | Yes | Yes | No | Lowest |
| Simple | No | Yes | No | Low |
| First-arrival | No (at goal) | Yes (prefixes) | Yes | Medium |
| Goal-reaching | No (at goal) | No | Yes | Highest |

### 4.3 Structural Justification for Goal-Reaching Geometry

Under goal-oriented semantics — where the system is evaluated by whether it
reaches a target state — non-goal-terminating paths introduce an
*intensity inflation artifact*: partial paths that end before reaching any
goal still contribute intensity, potentially dominating the contribution of
paths that actually reach the goal.

**Proposition 4** (Intensity Inflation).
*Let $a$ be an action with $k$ goal-reaching paths and $m$ non-goal
prefixes within horizon $h$, and let $a'$ be an action with $k'$
goal-reaching paths and $m'$ non-goal prefixes. If $m \gg m'$ while
$k < k'$, then under $G_{\text{simple}}$ or $G_{\text{prefix}}$,
action $a$ may have higher intensity $I(a) > I(a')$ despite having fewer
goal-reaching continuations.*

*Under $G_{\text{goal}}$, only the $k$ and $k'$ goal-reaching paths
contribute, and the inflation artifact is eliminated.*

**Demonstration** (Gordian Trap). Consider the Gordian Trap domain
(Appendix B.2). From state START, action A1 leads to a decoy path-family with
one short path (A1→A2→GOAL) and one loop path
(A1→L1→L2→L3→GOAL) that creates strong phase
opposition ($|\Delta\Theta| \approx \pi$). Action B1 leads to a single
coherent path (B1→B2→GOAL).

Under $G_{\text{simple}}$ at horizon $h = 5$: the loop path through A1
generates many non-goal prefixes
(A1→L1, A1→L1→L2, ...) that inflate $I(\text{A1})$. Amplitude agrees
with greedy, selecting the decoy A1.

Under $G_{\text{goal}}$ at horizon $h = 5$: only goal-reaching paths
contribute. The two A1-family paths exhibit destructive interference
($|\Delta\Theta| \approx 3.26 \approx \pi$), reducing $I(\text{A1})$ to
approximately 2% of its incoherent value, while $I(\text{B1})$ remains
coherent. Amplitude correctly selects B1, escaping the trap.

### 4.4 Empirical Geometry Comparison

Across four benchmark domains (Diamond, Gordian Trap, G5 Multi-Goal, Invoice
Workflow), we observe:

1. **Prefix $\equiv$ First-arrival** on all tested topologies (100%
   agreement across 380 scanned graphs).
2. **Simple $\approx$ Prefix** with 97.6% agreement rate.
3. **Goal-reaching differs exclusively** on 30.3% of scanned graphs —
   these are exactly the cases where interference-based routing provides
   advantage (§7).

**Result.** Simple geometry ($G_{\text{simple}}$) is a robust default for
exploratory analysis. Goal-reaching geometry ($G_{\text{goal}}$) is required
for trap domains under goal-oriented semantics.

---

## 5. Hybrid Controller

This section formalizes the operational controller that uses the amplitude
theory from §3–4 to make transition decisions.

### 5.1 Greedy Controller

**Algorithm 1** (Greedy Selection).
Given current state $x$ and admissible successors $N^+(x)$:
1. For each $y \in N^+(x)$, compute $S_{\text{eff}}(x \to y)$.
2. Select $y^* = \arg\min_{y \in N^+(x)} S_{\text{eff}}(x \to y)$.
3. If $N^+(x) = \emptyset$, *escalate* (DEAD\_END).

The greedy controller is deterministic and purely local: it considers only
single-edge tensions, not multi-hop path structure. This locality makes it
vulnerable to *structural traps* — states where the locally cheapest
transition leads toward a suboptimal or dead-end region, while a more
expensive first step would lead to a globally better path.

### 5.2 Amplitude Overlay

**Algorithm 2** (Bounded Amplitude Analysis).
Given current state $x$, horizon $h$, geometry $G$, and goal set
$\mathcal{T}$:
1. Enumerate all paths in $\mathcal{P}_G(x, a, h)$ for each $a \in N^+(x)$.
2. For each action $a$, compute $\Psi_G(a) = \sum_{p} \Psi(p)$.
3. Compute $I(a) = |\Psi_G(a)|^2$ and $P(a) = I(a) / \sum_{a'} I(a')$.
4. The *amplitude choice* is $a^* = \arg\max_{a} I(a)$.

**Computational complexity.** Path enumeration is $O(k^h)$ where $k$ is the
maximum branching factor and $h$ is the horizon. For the benchmark domains in
this paper ($k \leq 5$, $h \leq 5$), this is tractable. Scalability to larger
graphs is discussed in §9.

### 5.3 Hybrid Arbitration

**Algorithm 3** (AMPLITUDE\_ON\_DISAGREE).
Given greedy choice $y_g$ and amplitude choice $y_a$:
1. If $y_g = y_a$: follow greedy (agreement — amplitude confirms).
2. If $y_g \neq y_a$: follow amplitude (disagreement — amplitude overrides).
3. Safety conditions:
   - If amplitude overlay produces no valid result (escalation, empty paths):
     follow greedy.
   - Record override event for metrics.

**Proposition 5** (Monotonicity on Acyclic Graphs).
*On acyclic graphs with $G_{\text{goal}}$ geometry, the hybrid controller
never performs worse than greedy: if greedy reaches the goal, hybrid reaches
the goal at least as fast. If greedy is trapped, hybrid may escape.*

*Proof sketch.* On acyclic graphs, greedy termination is guaranteed (finite
paths, no revisits). When hybrid agrees with greedy, behavior is identical.
When hybrid overrides, the amplitude analysis has identified that a different
first hop leads to higher total intensity toward the goal set, which correlates
with better path structure. On acyclic trap topologies (e.g., Gordian), this
override is exactly the trap escape mechanism. $\square$

**Proposition 6** (Gordian Escape).
*On Gordian-class traps with $G_{\text{goal}}$ geometry and sufficient horizon
($h \geq 5$), the hybrid controller always escapes the trap by selecting the
non-decoy action.*

*Proof sketch.* The decoy path-family exhibits phase opposition
($|\Delta\Theta| \approx \pi$), causing destructive interference that reduces
$I(\text{decoy})$ to $\approx 2\%$ of its incoherent value. The non-decoy
path has $I > 0$ (single coherent path). Therefore $I(\text{non-decoy}) >
I(\text{decoy})$ and the amplitude choice overrides greedy. $\square$

**Proposition 7** (Determinism).
*The hybrid controller under AMPLITUDE\_ON\_DISAGREE mode is deterministic:
identical input (graph, state, historization) always produces the same
output.*

*Proof.* Every step in Algorithms 1–3 is deterministic: $\arg\min$ and
$\arg\max$ over finite sets with real-valued scores. Ties are broken by a
fixed ordering. No randomness is introduced at any stage. $\square$

### 5.4 Born Sampling Mode

In addition to the deterministic AMPLITUDE\_ON\_DISAGREE mode, E₀ supports
a stochastic mode:

**Algorithm 4** (BORN\_SAMPLING).
Given normalized intensities $P(a)$ for each $a \in N^+(x)$:
1. Draw action $a$ from the categorical distribution with $\Pr(a) = P(a)$.
2. Always override greedy (no agreement check).

This mode trades determinism for exploration: it samples from the
amplitude-induced distribution rather than selecting the maximum. Its
relationship to the deterministic mode is investigated in §6.

### 5.5 Operational Metrics

The hybrid controller records the following metrics per run:
- **Override count**: number of steps where amplitude overrode greedy.
- **Override rate**: override count / total steps.
- **Agreement rate**: 1 − override rate.
- **Override confidence**: $P_{\text{best}} - P_{\text{second}}$ at each
  override point (higher = more decisive override).

---

## 6. Central Result: Geometry Dominates Decision Rule

This section presents the main empirical finding of this paper: on
trap-containing domains, the choice of summation geometry has greater impact
on success than the choice of decision rule. We state this as an empirically
demonstrated theorem.

### 6.1 Experimental Setup

We compare two decision rules and two summation geometries on the Gordian
Trap domain (Appendix B):

**Decision rules:**
- *Argmax*: $a^* = \arg\max_a I(a)$ (deterministic), implemented as
  AMPLITUDE\_ON\_DISAGREE.
- *Born sampling*: $a \sim P(a) \propto I(a)$ (stochastic), implemented as
  BORN\_SAMPLING.

**Summation geometries:**
- $G_{\text{simple}}$: all simple (non-repeating) paths within horizon.
- $G_{\text{goal}}$: only goal-reaching paths within horizon.

This yields a $2 \times 2$ design. For each cell, we run 50–100 independent
trials with fixed random seeds.

### 6.2 Results

**Table 5: Success rates on Gordian Trap (geometry × decision rule)**

| | $G_{\text{simple}}$ | $G_{\text{goal}}$ |
|---|---|---|
| **Argmax** | 0% (0/50) | 100% (50/50) |
| **Born sampling** | ≈ 10–24% (varies) | ≈ 96% (≥80/100) |

**Interpretation.** The dominant effect is geometrical:

- With $G_{\text{simple}}$: *both* rules fail. Argmax is trapped because
  amplitude agrees with greedy (non-goal prefixes inflate the decoy). Born
  sampling occasionally escapes by randomly selecting the non-decoy, but
  this is chance, not structural insight.

- With $G_{\text{goal}}$: *both* rules succeed. The goal-reaching geometry
  exposes the destructive interference in the decoy path-family.
  Argmax always takes the correct action. Born sampling takes it with high
  probability ($P(\text{B1}) \gg P(\text{A1})$).

**Empirical Result 1** (Geometry Dominates Decision Rule).
*On Gordian-class trap domains, the transition from $G_{\text{simple}}$ to
$G_{\text{goal}}$ changes the success rate from 0% to 100% for the
deterministic rule and from $\approx$12% to $\approx$96% for the stochastic
rule. The transition from argmax to Born sampling under a fixed geometry
changes success by at most 24 percentage points (and typically ≤ 4). Therefore,
geometry choice dominates decision rule choice.*

**Remark.** This result has an analogy in machine learning: *feature
selection matters more than model choice* (a well-chosen feature set makes
even simple models succeed; a poor feature set defeats sophisticated models).
In E₀, the summation geometry plays the role of feature selection — it
determines which structural information reaches the decision mechanism.

### 6.3 Complementary Evidence: Diamond Domain

On the Diamond domain (no traps, two symmetric paths to goal):
- Both argmax and Born sampling reach the goal with 100% success under all
  geometries.
- Born sampling varies the chosen path (exploring both routes), while argmax
  always takes the same route.
- Steps to goal are identical for both modes (all paths have equal length).

This confirms that geometry × rule interaction matters primarily in
trap-containing topologies. On benign topologies, the choice is irrelevant.

---

## 7. Topology Classification: When Does Interference Help?

Not all graph topologies benefit from interference-based routing. This
section identifies structural predictors for when amplitude overlay provides
advantage over greedy control.

### 7.1 Methodology

We generate 380 directed graphs:
- **180 structured:** 60 triangles, 60 diamonds, 60 gordian-lite instances.
- **200 random:** varying state counts, edge densities, and parameter ranges.

For each graph, at state START with goal set {GOAL}, we compute:
1. The greedy choice (Algorithm 1).
2. The amplitude choice under $G_{\text{goal}}$ (Algorithm 2).
3. Whether they disagree (*override*).

We then correlate override occurrence with topological features.

### 7.2 Results

**Table 6: Override rates by topology class**

| Topology | Override rate | Path families | Phase opposition |
|----------|-------------|---------------|-----------------|
| Triangle (single-family) | 0% | 1 | N/A |
| Diamond (two-family) | 36.7% | 2 | Variable |
| Gordian-lite (two-family + loop) | 93.3% | 2 | Strong ($>\pi/4$) |
| Random | Varies | Varies | Varies |

### 7.3 Structural Predictors

**Proposition 8** (Path-Family Requirement).
*Override requires at least two path families from START (i.e., $|N^+(x)|
\geq 2$). Single-family topologies never produce overrides under any geometry.*

*Proof.* If $|N^+(x)| = 1$, there is exactly one admissible action. Both
greedy and amplitude must select it. $\square$

**Empirical Finding 1** (Phase Opposition Predictor).
Phase opposition $|\Delta\Theta| > \pi/2$ between path families is the
strongest predictor of override occurrence. Among Gordian-lite instances:
- Instances with $|\Delta\Theta| > \pi/2$: override rate $> 90\%$.
- Instances with $|\Delta\Theta| < \pi/4$: override rate $< 10\%$.

The correlation between phase opposition and override is $+25.1\%$ across
the full 380-graph scan.

**Empirical Finding 2** ($G_{\text{goal}}$ Exclusivity).
$G_{\text{goal}}$ produces exclusive overrides (i.e., overrides not produced
by any other geometry) on 30.3% of scanned graphs. These are exactly the
cases where non-goal prefix inflation masks the true interference pattern
under other geometries.

### 7.4 Predictive Rules

Based on the topology scan, we identify three conditions for productive use
of amplitude-based routing:

1. **Multiple path families** ($|N^+(x)| \geq 2$): necessary condition.
2. **Phase opposition** ($|\Delta\Theta| > \pi/2$ between families): strong
   predictor.
3. **Goal-reaching geometry active**: required to expose interference masked
   by prefix inflation.

When *none* of these conditions is met — linear chains, trees,
single-family topologies — greedy control is sufficient and the amplitude
overlay adds no value.

### 7.5 Grid World Benchmark

To validate E₀'s operational mechanisms on a standard planning domain, we
compare three methods on $5 \times 5$ grid worlds:

- **Naive Greedy**: picks the neighbor with lowest $\Delta$ at each step.
  No memory, no revisit penalty, no escalation.
- **E₀ Greedy**: the full E₀ controller in GREEDY mode — includes revisit
  penalty ($\alpha = 2.0$, $k = 3$) and typed escalation (§5.1), but no
  amplitude overlay.
- **A\***: optimal shortest-path baseline with Manhattan heuristic.

Three grid variants test distinct failure modes:

**V1 — Detour Wall.** A vertical wall at column 2 (rows 1–4) blocks the
direct path; the only gap is at row 0. Naive greedy reaches the wall and
oscillates (0% success). E₀ Greedy's EXHAUSTED escalation detects the cycle
and routes through the gap (100%, 16 steps vs.\ optimal 8).

**V2 — Dead-End Lure.** A moderate-$\Delta$ dead-end ($\Delta = 0.20$)
attracts greedy agents into a pocket walled off from the goal. Naive greedy
enters and is trapped (0%). E₀'s revisit penalty raises the penalized
tension on lure edges ($0.20 \times 3.0 = 0.60$) above exit tension
($\approx 0.45$), enabling escape (100%, 10 steps).

**V3 — Trap Loop.** A 3-cell cycle with $\Delta = 0.18$ creates a locally
attractive loop on the direct path to goal. Naive greedy enters the loop
and cycles indefinitely (0%). E₀'s revisit penalty immediately raises loop
tension above exit alternatives, and the controller reaches the goal in 8
steps (optimal).

**Table 6: Grid World Benchmark Results (10 trials per method)**

| Variant | Naive Greedy | E₀ Greedy | A\* (optimal) |
|---------|-------------|-----------|---------------|
| V1 Detour Wall | 0% | 100% (16 steps) | 8 steps |
| V2 Dead-End Lure | 0% | 100% (10 steps) | 8 steps |
| V3 Trap Loop | 0% | 100% (8 steps) | 8 steps |

**Interpretation.** The revisit penalty and escalation mechanisms of the E₀
controller — derived from historization (§3.3) — are sufficient to escape
all three trap types. The amplitude overlay is not tested here; it is
designed for structured decision points with interference-producing topology
(§6–7). The benchmark source code is included in
`e0_controller/benchmark_gridworld.py`.

---

## 8. Implementation and Reproducibility

### 8.1 Implementation Overview

The E₀ framework is implemented in Python 3.11 in approximately 3,000 lines
of code in the `e0_controller/` package. The implementation directly
mirrors the mathematical definitions in §3: each definition corresponds to
a named function with matching semantics.

| Module | Function | Definition |
|--------|----------|------------|
| `landscape.py` | `difference(x, y)` | Def. 2 |
| `landscape.py` | `effective_resistance(x, y)` | Def. 6 |
| `landscape.py` | `transition_field(x, y)` | Def. 10 |
| `potential.py` | `phi(L, x)` | Def. 11 |
| `potential.py` | `v_grad(L, x, y)` | Def. 12 |
| `potential.py` | `v_rot(L, x, y)` | Def. 13 |
| `connection.py` | `omega(L, x, y)` | Def. 14 |
| `connection.py` | `theta(L, path)` | Def. 15 |
| `wavepath.py` | `psi(L, path)` | Def. 17 |
| `wavepath.py` | `sum_paths(L, paths)` | Def. 18 |
| `amplitude_overlay.py` | `analyze_controller_state()` | Algorithm 2 |
| `controller.py` | `select_next()` | Algorithm 1 |
| `controller.py` | `select_hybrid()` | Algorithm 3 |
| `historization.py` | `update(e, outcome)` | Def. 4 |
| `historization.py` | `delta_H(e)` | Def. 5 |

### 8.2 Test Registry

The implementation is validated by 936 unit tests across 27 test files,
organized into 8 formal test paths (A–H). Each path targets a specific
structural claim:

| Path | Focus | Tests | Key claim |
|------|-------|-------|-----------|
| A | Omega uniqueness | — | Connection antisymmetry \& uniqueness |
| B | Historization × Gordian | — | Learning interacts with trap geometry |
| C | Reflection hybrid | — | Hybrid controller integration |
| D | Born regime axioms | — | Born criterion prerequisites |
| E | Dynamic horizons | — | Horizon sensitivity |
| F | Confidence override | — | Override confidence gating |
| G | MemOS geometry | — | Persistence of geometry state |
| H | Born sampling | 27 | Geometry > rule (Empirical Result 1) |

22 verified claims (C1–C22) are maintained in a test registry with
derived/empirical/heuristic classification.

### 8.3 Reproducibility

All experiments use fixed random seeds. All benchmark domains are defined
in test code with exact parameter values (no external data dependencies).
To reproduce:

```
python -m unittest discover -s e0_controller -p "test_*.py"
```

The code repository is open-source and tagged at the version used in this
paper.

---

## 9. Limitations and Falsification Targets

### 9.1 Status of Formal Claims

We distinguish three categories following the framework's own honesty map
(Table 1):

**Derived** (follows from the structural chain):
- Tension, coherence, transition field (Defs. 7–10).
- Helmholtz decomposition, potential (Defs. 11–13).
- Connection antisymmetry (Def. 14).
- Holonomy independence (Theorem 1).
- Interference existence (Proposition 2).
- Zero-holonomy reduction (Proposition 3).

**Empirical** (demonstrated through tests, not analytically proven):
- Geometry dominates decision rule (Empirical Result 1).
- Topology classification predictors (§7).
- Goal-reaching geometry resolves Gordian traps (Proposition 6).
- Destructive interference factor ($\approx 2\%$) in Gordian domain.

**Heuristic** (works operationally, not yet derived):
- Revisit penalty in greedy controller.
- Escalation logic type classification.
- Specific parameter choices ($\rho = 0.9$, $\lambda_s = 0.15$,
  $\lambda_f = 0.20$, $\delta_{\max} = 3.0$).
- Phase $\Theta$ — derived up to the gauge class defined by the Helmholtz
  decomposition and antisymmetric extraction (see §3.6, Gauge Freedom
  remark). Within this gauge class, $\Theta$ is uniquely determined;
  across gauge classes, the holonomy $\text{Hol}(\gamma)$ and interference
  effects remain invariant.

### 9.2 Computational Limitations

Path enumeration under all geometries is $O(k^h)$ where $k$ is the maximum
branching factor and $h$ is the horizon. This is tractable for $k \leq 5$,
$h \leq 10$, but does not scale to large dense graphs.

We identify three approximation strategies for future work:

1. **Interference-aware pruning.** During path enumeration, discard path
   families whose coherence $C(p) < \epsilon_{\text{prune}}$ falls below a
   threshold. Low-coherence paths contribute negligible amplitude and cannot
   produce significant interference. This reduces the effective branching
   factor without altering high-signal decisions.

2. **Stochastic path sampling.** Instead of exhaustive enumeration, sample
   $N$ paths per action according to a distribution biased toward
   low-tension edges. The amplitude estimate $\hat{\Psi}_G(a) =
   \frac{1}{N}\sum_{i=1}^{N} \Psi(p_i)$ converges to the true amplitude
   as $N \to \infty$. The key question — whether interference structure
   is preserved under sampling — is an open empirical problem.

3. **Truncated DFS with interference budget.** Enumerate paths in DFS
   order, maintaining a running amplitude sum. Terminate enumeration for
   an action when the marginal change $|\Delta\Psi| / |\Psi_{\text{acc}}|$
   falls below a tolerance, indicating that further paths do not
   qualitatively change the interference pattern.

These strategies are not explored in this paper but represent natural
extensions of the bounded enumeration framework.

### 9.3 Domain Limitations

All benchmark domains are synthetic. The framework has not been validated on
real-world planning, routing, or workflow domains. The LLM integration layer
exists in the implementation but is not part of the theoretical contribution.

### 9.4 Active Falsification Targets

We identify specific predictions that, if falsified, would weaken or disprove
central claims:

1. **Anti-monotonicity:** Find a graph where hybrid consistently
   underperforms greedy (currently not observed in 380 graphs).
2. **Phase irrelevance:** Find a domain where $\Theta$ does not influence
   interference outcomes (would weaken Theorem 1's significance).
3. **Geometry irrelevance:** Demonstrate that geometry choice is
   irrelevant on some non-trivial topology class (would weaken Empirical Result 1).
4. **Historization instability:** Show that interference-based routing
   becomes unstable under historization updates (currently stable across
   12 tests in 4 scenarios).

---

## 10. Discussion

### 10.1 Relation to Path-Integral Control

The E₀ framework bears structural resemblance to path-integral control
theory (Kappen, 2005; Todorov, 2007), where optimal control is expressed as a
sum over trajectories weighted by exponentials of costs. The key differences
are:

1. **Derivation vs. postulation.** In path-integral control, the amplitude
   structure (Boltzmann-like weighting $\exp(-S)$) is postulated from
   physics analogies. In E₀, the complex amplitude $\Psi = \exp(-S + i\Theta)$
   is derived from structural primitives through the Helmholtz decomposition
   of the transition field.

2. **Phase structure.** Path-integral control typically uses real-valued
   weights (no phase). E₀'s phase $\Theta$ emerges from the rotational
   (non-conservative) component of the transition field and enables
   *destructive* interference — an effect absent in classical path-integral
   control.

3. **Discrete setting.** E₀ operates on finite directed graphs. No
   continuous limit, Wiener measure, or stochastic calculus is required.

### 10.2 Structural vs. Statistical Learning

E₀ learns through historization — resistance updates that modify the
transition landscape based on realized outcomes. This is fundamentally
different from gradient-based learning:

- **No objective function:** there is no loss to minimize. Transitions alter
  future structure directly.
- **No parameter space:** the learning surface is the graph itself (edge
  resistances), not a separate parameter vector.
- **Bounded drift:** clipping ($\delta_{\max}$) prevents unbounded
  historization, unlike unconstrained gradient descent.

### 10.3 The Geometry Insight

The finding that summation geometry dominates decision rule (Empirical Result 1) has
a structural analogy in machine learning: *kernel choice matters more than
model choice* in kernel methods, and *feature selection matters more than
classifier choice* in classification. In E₀, the summation geometry
determines which structural information reaches the decision mechanism. A
poor geometry feeds misleading information to any decision rule — deterministic
or stochastic. A good geometry makes even a simple rule effective.

This suggests a practical design principle: when deploying interference-based
routing, invest in geometry selection (which requires domain knowledge about
what constitutes "reaching the goal") before tuning the decision rule.

### 10.4 Implications for AI System Design

E₀ demonstrates that structural decision layers — built from graph primitives
rather than reward functions — can provide robust trap avoidance without
reinforcement learning, Monte Carlo simulation, or explicit heuristic design.
The hybrid architecture (domain-agnostic structural core + domain-specific
evaluation function) offers a separation of concerns: the mathematical
machinery of interference is generic, while the definition of $\Delta$, $R_0$,
and the goal set $\mathcal{T}$ encodes domain semantics.

A key design principle emerges: E₀ is not "probability-free" — the
normalized intensity $P(a)$ is a probability distribution. Rather, E₀
replaces *assumed* probability with *emergent* probability: the distribution
over actions is a derived consequence of amplitude interference, not an
axiomatic input. This inverts the standard construction in decision theory,
where probabilities are primitive and utilities are derived.

More broadly, interference acts as a *non-local decision signal*: it
aggregates structural information across entire path families — including
destructive cancellation from topological traps — without explicit search
heuristics, lookahead trees, or learned value functions. This non-locality
is what enables trap avoidance: the interference pattern at the decision
point encodes information about distant graph structure that no local
(one-step) evaluation can access.

---

## 11. Conclusion

We have introduced E₀, a formal framework for discrete transition systems
that derives complex path amplitudes from three structural primitives:
difference ($\Delta$), resistance ($R$), and historization ($H$). The main
contributions are:

1. **A constructive derivation chain** from primitives to complex amplitudes
   $\Psi = \exp(-S + i\Theta)$ exhibiting interference (§3), with a proven
   Holonomy Independence Theorem (Theorem 1) establishing that phase
   differences depend only on path-local quantities.

2. **Four summation geometries** with formal definitions and empirical
   comparison, identifying goal-reaching geometry as structurally necessary
   for trap domains (§4).

3. **A hybrid controller** that uses amplitude-based interference to override
   greedy decisions when structural traps are detected (§5).

4. **The geometry-dominance result** (Empirical Result 1): on trap-containing
   domains, the choice of summation geometry determines success or failure,
   while the choice of decision rule (deterministic vs. stochastic) is
   secondary (§6).

5. **A topology classification** across 380 graphs identifying path-family
   count and phase opposition as structural predictors for interference
   utility (§7).

6. **A grid world benchmark** demonstrating that E₀'s operational mechanisms
   (revisit penalty, escalation) achieve 100% success on three trap domains
   where memoryless greedy fails completely (§7.5).

All claims are explicitly classified as derived, empirical, or heuristic
(§9.1). The framework does not claim continuous-limit validity, probabilistic
guarantees, or real-world deployment evidence. It offers a formally explicit,
reproducible, and honestly scoped alternative to probability-first and
reward-first approaches to decision-making in structured transition systems.

A companion paper (in preparation) extends the E₀ framework with SU(2)
spinor structure, investigating the relationship between the derived
amplitude and Born-rule probability, and the emergence of non-commutative
phase geometry.

---

## Appendices

### Appendix A. Proof Details for Theorem 1 (Holonomy Independence)

Let $p_1 = (x, a_1, a_2, \ldots, y)$ and $p_2 = (x, b_1, b_2, \ldots, y)$
be two directed paths from $x$ to $y$.

**Step 1.** Expand $\Theta(p_1)$:

$$\Theta(p_1) = \sum_{e \in p_1} \omega(e) = \sum_{e \in p_1} \frac{1}{2}\bigl(v_{\text{rot}}(e) - v_{\text{rot}}(\bar{e})\bigr)$$

**Step 2.** Since $v_{\text{rot}} = v - v_{\text{grad}}$ and
$v_{\text{grad}}(x,y) = \Phi(x) - \Phi(y)$:

$$\sum_{e \in p_1} v_{\text{grad}}(e) = \Phi(x) - \Phi(y)$$

by telescoping. The same holds for $p_2$:

$$\sum_{e \in p_2} v_{\text{grad}}(e) = \Phi(x) - \Phi(y)$$

**Step 3.** Therefore in $\Delta\Theta = \Theta(p_1) - \Theta(p_2)$, all
$v_{\text{grad}}$ terms cancel, leaving:

$$\Delta\Theta = \frac{1}{2}\sum_{e \in p_1}\bigl(v(e) - v(\bar{e})\bigr) - \frac{1}{2}\sum_{e \in p_2}\bigl(v(e) - v(\bar{e})\bigr)$$

Each term $v(e)$ depends only on the edge-local quantities $\Delta(e)$ and
$R_{\text{eff}}(e)$. No reference to $\Phi$ or to edges outside $p_1 \cup
p_2$ remains. $\square$

**Numerical verification.** On the Gordian Trap test domain (§4.3),
$\Delta\Theta \approx 3.26$ matches the predicted
$\frac{1}{2}(\sum v_{\text{loop}} - \sum v_{\text{short}})$ to 6 decimal
places (verified in test suite, Path A).

### Appendix B. Benchmark Domain Specifications

#### B.1 Diamond Domain

A two-family interference domain with a dead-end trap.

**States:** $\{S, A, B, C, M, N, Z\}$

**Edges and parameters:**

| Edge | $\Delta$ | $R_0$ | $S_0$ |
|------|----------|-------|-------|
| $S \to A$ | 0.30 | 0.60 | 0.180 |
| $S \to B$ | 0.35 | 0.70 | 0.245 |
| $S \to C$ | 0.30 | 0.50 | 0.150 |
| $A \to M$ | 0.20 | 0.40 | 0.080 |
| $M \to Z$ | 0.15 | 0.30 | 0.045 |
| $B \to N$ | 0.25 | 0.60 | 0.150 |
| $N \to Z$ | 0.20 | 0.40 | 0.080 |
| $A \to S$ | 0.80 | 2.00 | 1.600 |
| $B \to S$ | 0.50 | 1.50 | 0.750 |
| $M \to N$ | 0.30 | 0.50 | 0.150 |

**Design:** Greedy selects $S \to C$ (lowest $S_0 = 0.15$), but $C$ is a
dead-end. Upper path ($S \to A \to M \to Z$) and lower path
($S \to B \to N \to Z$) have similar tensions but different phase
accumulations due to asymmetric back-edges, creating interference at $Z$.

#### B.2 Gordian Trap Domain

A holonomy-tuned trap domain where destructive interference identifies the
decoy.

**States:** $\{\text{START}, \text{A1}, \text{A2}, \text{L1}, \text{L2}, \text{L3}, \text{B1}, \text{B2}, \text{GOAL}\}$

**Edges and parameters:**

| Edge | $\Delta$ | $R_0$ | $S_0$ |
|------|----------|-------|-------|
| START $\to$ A1 | 0.30 | 0.30 | 0.090 |
| A1 $\to$ A2 | 0.40 | 0.30 | 0.120 |
| A2 $\to$ GOAL | 0.40 | 0.30 | 0.120 |
| A1 $\to$ L1 | 2.00 | 0.05 | 0.100 |
| L1 $\to$ L2 | 2.00 | 0.05 | 0.100 |
| L2 $\to$ L3 | 2.00 | 0.05 | 0.100 |
| L3 $\to$ GOAL | 2.00 | 0.05 | 0.100 |
| START $\to$ B1 | 0.50 | 0.40 | 0.200 |
| B1 $\to$ B2 | 0.30 | 0.35 | 0.105 |
| B2 $\to$ GOAL | 0.30 | 0.30 | 0.090 |

**Design:** Greedy selects START $\to$ A1 ($S_0 = 0.09 < 0.20$). Path
A1 has two sub-paths to GOAL: A-short (A1→A2→GOAL, low
$v$) and A-loop (A1→L1→L2→L3→GOAL, high $v$ due to
$\Delta = 2.0, R = 0.05$). The phase difference
$|\Delta\Theta| \approx 3.26 \approx \pi$ produces destructive interference,
reducing $I(\text{A1})$ to $\approx 2\%$ of its incoherent sum.
Path B (START→B1→B2→GOAL) is a single coherent path.
Under $G_{\text{goal}}$, amplitude correctly selects B1.

#### B.3 G5 Multi-Goal Domain

A three-family domain with multiple goal states for testing Born sampling and
multi-goal coverage. Three parallel paths from $S$ to goals $\{G1, G2, G3\}$
with varying parameters.

#### B.4 Grid World Domains

Three $5 \times 5$ grid worlds for testing operational mechanisms (§7.5).
All use 4-connected grids with start $(0,0)$ and goal $(4,4)$. Edge $\Delta$
defaults to $\Delta_0 + 0.5 \cdot d_{\text{target}} / (R + C)$ where
$d_{\text{target}}$ is the Manhattan distance from target cell to goal and
$\Delta_0 = 0.3$. Specific edges have $\Delta$ overrides as noted below.

**V1 — Detour Wall.** Wall at column 2, rows 1–4. Only gap at row 0.
No $\Delta$ overrides. A* optimal: 8 steps.

```
    0 1 2 3 4
0   S . . . .
1   . . # . .
2   . . # . .
3   . . # . .
4   . . # . G
```

**V2 — Dead-End Lure.** Walls at (2,1), (2,2), (4,1). Edges into and
within the dead-end pocket have $\Delta = 0.20$. A* optimal: 8 steps.

```
    0 1 2 3 4
0   S . . . .
1   . . . . .
2   . # # . .
3   L L . . .
4   L # . . G
```

**V3 — Trap Loop.** Wall at (2,2). Edges between trap cells (1,1),
(1,2), (2,1) have $\Delta = 0.18$; entry edges have $\Delta = 0.20$.
A* optimal: 8 steps.

```
    0 1 2 3 4
0   S . . . .
1   . T T . .
2   . T # . .
3   . . . . .
4   . . . . G
```

Source code: `e0_controller/benchmark_gridworld.py`.

### Appendix C. Derived / Empirical / Heuristic Classification (Table 1)

| Component | Status | Evidence |
|-----------|--------|----------|
| $\Delta, R_0, H$ (primitives) | Derived | Axiomatic basis |
| $S = \Delta \cdot R_{\text{eff}}$ | Derived | Def. 7 |
| $C = \exp(-S)$ | Derived | Def. 9, Prop. 1 |
| $v = \Delta \cdot \exp(-S)$ | Derived | Def. 10 |
| $\Phi$ (Helmholtz potential) | Derived | Def. 11 (Laplacian solve) |
| $v_{\text{grad}}, v_{\text{rot}}$ | Derived | Defs. 12–13 |
| $\omega$ (connection) | Derived | Def. 14 |
| Holonomy independence | **Derived** | Theorem 1 (proven) |
| $\Psi = \exp(-S + i\Theta)$ | Derived (structural) | Def. 17 |
| $I = |\Psi|^2$ (intensity) | Derived (conditional) | Def. 19 |
| Interference existence | **Derived** | Proposition 2 (proven) |
| Destructive factor $\approx 2\%$ | **Empirical** | Gordian Trap tests |
| Geometry dominates rule | **Empirical** | Empirical Result 1 (50–100 trials) |
| Topology predictors | **Empirical** | 380-graph scan |
| Phase $\Theta$ from $v_{\text{rot}}$ | Heuristic | Structurally motivated but not unique |
| Revisit penalty | Heuristic | Operational stabilization |
| Escalation types | Heuristic | Operational safety |
| Parameters ($\rho, \lambda_s, \lambda_f$) | Heuristic | Chosen by tuning |

### Appendix D. Test Registry Summary

22 verified claims (C1–C22) organized by formal test path. Each claim
references specific test functions and specifies its evidence category
(derived, empirical, or heuristic). Full registry available in the code
repository.

---

## References

[1] H. J. Kappen. "Path integrals and symmetry breaking for optimal control theory." *Journal of Statistical Mechanics: Theory and Experiment*, 2005(11):P11011, 2005.

[2] E. A. Theodorou, J. Buchli, and S. Schaal. "A generalized path integral control approach to reinforcement learning." *Journal of Machine Learning Research*, 11:3137–3181, 2010.

[3] E. Todorov. "Linearly-solvable Markov decision problems." In *Advances in Neural Information Processing Systems (NeurIPS)*, pp. 1369–1376, 2007.

[4] H. J. Kappen, V. Gómez, and M. Opper. "Optimal control as a graphical model inference problem." *Machine Learning*, 87(2):159–182, 2012.

[5] S. Levine. "Reinforcement learning and control as probabilistic inference: Tutorial and review." arXiv preprint arXiv:1805.00909, 2018.

[6] B. D. Ziebart, A. Maas, J. A. Bagnell, and A. K. Dey. "Maximum entropy inverse reinforcement learning." In *Proceedings of the AAAI Conference on Artificial Intelligence*, pp. 1433–1438, 2008.

[7] T. Haarnoja, A. Zhou, P. Abbeel, and S. Levine. "Soft actor-critic: Off-policy maximum entropy deep reinforcement learning with a stochastic actor." In *International Conference on Machine Learning (ICML)*, pp. 1861–1870, 2018.

[8] D. Aharonov, A. Ambainis, J. Kempe, and U. Vazirani. "Quantum walks on graphs." In *Proceedings of the 33rd Annual ACM Symposium on Theory of Computing (STOC)*, pp. 50–59, 2001.

[9] E. Farhi and S. Gutmann. "Quantum computation and decision trees." *Physical Review A*, 58(2):915, 1998.

[10] H. J. Briegel and G. De las Cuevas. "Projective simulation for artificial intelligence." *Scientific Reports*, 2:400, 2012.

[11] J. Mautner, A. Makmal, D. Manzano, M. Tiersch, and H. J. Briegel. "Projective simulation for classical learning agents: A comprehensive investigation." *New Generation Computing*, 33(1):69–114, 2015.

[12] F. Flamini, A. Hamann, S. Jerbi, L. M. Trenkwalder, H. P. Nautrup, and H. J. Briegel. "Photonic architecture for reinforcement learning." *New Journal of Physics*, 22(4):045002, 2020.

[13] M. V. Berry. "Quantal phase factors accompanying adiabatic changes." *Proceedings of the Royal Society of London A*, 392(1802):45–57, 1984.

[14] B. Liu, Y. Tong, F. De Goes, and M. Desbrun. "Discrete connection and covariant derivative for vector field analysis and design." *ACM Transactions on Graphics*, 35(3):23:1–17, 2016.

[15] A. Singer and H.-T. Wu. "Vector diffusion maps and the connection Laplacian." *Communications on Pure and Applied Mathematics*, 65(8):1067–1144, 2012.

[16] S. Favoni, A. Ipp, D. I. Müller, and D. Schuh. "Lattice gauge equivariant convolutional neural networks." *Physical Review Letters*, 128(3):032003, 2022.

[17] T. S. Cohen, M. Weiler, B. Kicanaoglu, and M. Welling. "Gauge equivariant convolutional networks and the icosahedral CNN." In *International Conference on Machine Learning (ICML)*, pp. 1321–1330, 2019.

[18] Y. He, M. Xu, C. Adams, S. Bose, U. Bhatt, and M. Bronstein. "A gauge equivariant transformer." arXiv preprint arXiv:2310.12963, 2023.

[19] J. E. Gerken, J. Aronsson, O. Carlsson, H. Linander, F. Ohlsson, C. Petersson, and D. Persson. "Geometric deep learning and equivariant neural networks." *Artificial Intelligence Review*, 56:14605–14662, 2023.

[20] C. Bodnar, F. Di Giovanni, B. Chamberlain, P. Liò, and M. Bronstein. "Neural sheaf diffusion: A topological perspective on heterophily and oversmoothing in GNNs." In *Advances in Neural Information Processing Systems (NeurIPS)*, 2022.

[21] Z. Chen, L. Chen, S. Villar, and J. Bruna. "On the expressiveness of spectral invariants and categorical representations for graphs." In *Advances in Neural Information Processing Systems (NeurIPS)*, 2023.

[22] T. Schaul, D. Horgan, K. Gregor, and D. Silver. "Universal value function approximators." In *International Conference on Machine Learning (ICML)*, pp. 1312–1320, 2015.

[23] M. Andrychowicz, F. Wolski, A. Ray, J. Schneider, R. Fong, P. Welinder, B. McGrew, J. Tobin, P. Abbeel, and W. Zaremba. "Hindsight experience replay." In *Advances in Neural Information Processing Systems (NeurIPS)*, pp. 5048–5058, 2017.

[24] D. M. Roijers, P. Vamplew, S. Whiteson, and R. Dazeley. "A survey of multi-objective sequential decision-making." *Journal of Artificial Intelligence Research*, 48:67–113, 2013.

[25] F. Felten, L. N. Alegre, A. Nowé, A. Bazzan, E. G. Talbi, G. Danoy, and B. C. da Silva. "A toolkit for reliable benchmarking and research in multi-objective reinforcement learning." In *NeurIPS Datasets and Benchmarks Track*, 2023.

[26] R. V. Cowlagi and P. Tsiotras. "Shortest distance problems in graphs using history-dependent transition costs." *Discrete Applied Mathematics*, 161(7–8):1099–1120, 2013.

[27] S. Koenig and M. Likhachev. "D* Lite." In *Proceedings of the AAAI Conference on Artificial Intelligence*, pp. 476–483, 2002.

[28] M. Phillips, B. J. Cohen, S. Chitta, and M. Likhachev. "E-graphs: Bootstrapping planning with experience graphs." In *Robotics: Science and Systems (RSS)*, 2012.

[29] G. Tennenholtz, A. Hallak, G. Mannor, and S. Mannor. "Reinforcement learning with history-dependent dynamic contexts." In *International Conference on Machine Learning (ICML)*, pp. 10330–10340, 2021.

[30] T. Genewein, G. Delétang, A. Grau-Moya, L. K. Wenliang, M. Aitchison, T. Lattimore, M. Hutter, S. Legg, and J. Veness. "Memory and meta-learning as approximate Bayesian inference." In *Advances in Neural Information Processing Systems (NeurIPS)*, 2023.

---

*End of manuscript.*
