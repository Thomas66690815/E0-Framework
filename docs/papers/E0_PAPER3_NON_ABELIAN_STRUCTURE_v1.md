# Non-Abelian Structure in E₀: Per-Edge SU(2) Transport and Curvature Modulation

**Paper 3 — Draft v1.0**
**Date:** 2026-03-26
**Status:** Draft
**Prerequisite:** E₀ Formal Paper (v1.0), §1–§9

---

## Abstract

The E₀ framework derives, from three primitives (difference Δ, resistance R, historization H), a complex path amplitude Ψ(p) = exp(−S) · exp(iΘ) whose phase Θ is accumulated from an antisymmetric U(1) connection ω. This paper extends the phase structure from Abelian U(1) to non-Abelian SU(2). The extension is carried out in three stages. First, the scalar connection ω is promoted to an SU(2) edge transport U(x,y) = exp(−iω/2 · n̂ · σ⃗), where the rotation axis n̂ may vary per edge (§3). Second, the rotation axis is derived from the local Helmholtz geometry of the transition field, yielding a three-component su(2) connection A⃗ = (A₁, A₂, A₃) whose components encode vorticity gradient, face holonomy, and direct connection (§4). Third, the face holonomy is used to define an edge curvature κ and a topological modulation factor M_H = 1/(1+κ) that feeds back into the transition field v = Δ · M_H · exp(−S_eff) (§5). The resulting structure is non-commutative, path-order-dependent, and produces interference patterns in ℂ² that are strictly richer than U(1). All claims are verified numerically against 71 tests across four graph topologies. An experimental switch (curvature_modulation) allows runtime comparison of the modulated and unmodulated regimes. When disabled (default), all prior behavior is exactly preserved.

---

## 1. Introduction

### 1.1 Context

The E₀ formal framework [Paper 1] establishes a transition-centered system built from difference, resistance, and historization. Its mathematical core derives a dependency chain

$$
\Delta \to R_0 \to H \to \delta_H \to R_{\text{eff}} \to S \to C \to \Phi \to v_{\text{rot}} \to \omega \to \Theta \to \Psi
$$

culminating in a complex path amplitude $\Psi(p) = e^{-S(p)} \cdot e^{i\Theta(p)}$ that enables interference-based arbitration between competing transition paths [Paper 1, §9].

The connection $\omega$ in this chain is a real-valued antisymmetric quantity on directed edges:

$$
\omega(x,y) = \tfrac{1}{2}\bigl(v_{\text{rot}}(x,y) - v_{\text{rot}}(y,x)\bigr)
$$

It generates a U(1) phase $\Theta(p) = \sum_{e \in p} \omega(e)$ and yields scalar holonomy $\text{Hol}(\gamma) = \Theta(\gamma) \in \mathbb{R}$. This is sufficient to produce constructive and destructive interference in ℂ, and has been shown to enable topology-dependent override behavior in hybrid controllers [Paper 2, §5–6].

However, the U(1) structure has a fundamental limitation: all edge transports commute. The phase accumulated along a path $A \to B \to C$ is identical to $A \to C \to B$ as long as the same edges are traversed. Path *order* does not matter — only the edge *set*.

### 1.2 Motivation

In gauge theory, the step from Abelian U(1) to non-Abelian SU(2) is the step from electromagnetism to the weak nuclear force. The mathematical consequence is that parallel transport becomes path-order-dependent: traversing edges in different sequences produces different results, even when the same edges are used.

For E₀, the question is whether such non-Abelian structure can emerge from the existing transition framework without importing external assumptions. This paper shows that it can, in three stages:

1. **Per-edge rotation axes** (§3): The scalar ω already exists on every edge. By coupling it to a per-edge unit vector n̂(x,y) ∈ ℝ³ via SU(2) generators σ⃗, the transport becomes matrix-valued. Different axes on different edges produce non-commutativity.

2. **Geometry-derived axes** (§4): The axis n̂ need not be externally assigned. It can be derived from the local Helmholtz decomposition of the transition field, producing a three-component su(2) connection whose components have intrinsic geometric meaning.

3. **Curvature feedback** (§5): The face holonomy of triangles through an edge defines a local curvature κ, which modulates the transition field via M_H = 1/(1+κ). This closes a feedback loop: geometry → curvature → transition field → geometry.

### 1.3 Contributions

This paper makes the following contributions:

- **C1:** Extension of the E₀ path amplitude from ℂ to ℂ² via SU(2) spinor transport, with per-edge rotation axes (§3).
- **C2:** Derivation of a three-component su(2) connection from the Helmholtz structure of the transition field, without external parameters (§4).
- **C3:** Definition of edge curvature κ from face holonomy and a topological modulation factor M_H that feeds back into the transition field (§5).
- **C4:** Numerical verification across 71 tests on four graph topologies, with complete backward compatibility (§6).
- **C5:** Runtime experimental switch allowing comparison of modulated and unmodulated regimes (§5.4).

### 1.4 Scope and Honesty Statement

The SU(2) extension is mathematically well-defined and operationally realized. It is *not* claimed to be physically necessary or uniquely determined. The per-edge axis assignment (when not geometry-derived) is a degree of freedom. The curvature formula M_H = 1/(1+κ) is a candidate — the alternative M_H = exp(−κ) has the same asymptotic limits but different intermediate behavior. Both choices are reported.

The extension is introduced behind an experimental switch (`curvature_modulation=False` by default). The default runtime of E₀ is unchanged.

---

## 2. Preliminaries

We assume familiarity with the E₀ formal framework [Paper 1]. The following objects are used throughout:

| Symbol | Definition | Domain |
|--------|-----------|--------|
| $\Delta(x,y)$ | Structural difference | $\mathbb{R}_{\geq 0}$ |
| $R_{\text{eff}}(x \to y)$ | Effective resistance | $\mathbb{R}_{> 0}$ |
| $S(x \to y) = \Delta \cdot R_{\text{eff}}$ | Tension | $\mathbb{R}_{\geq 0}$ |
| $C(p) = e^{-S(p)}$ | Coherence | $(0, 1]$ |
| $v(x,y) = \Delta \cdot e^{-S}$ | Transition field | $\mathbb{R}_{\geq 0}$ |
| $v_{\text{rot}}(x,y)$ | Rotational component (Helmholtz) | $\mathbb{R}$ |
| $\omega(x,y)$ | Antisymmetric connection | $\mathbb{R}$ |
| $\Theta(p) = \sum \omega$ | Path phase | $\mathbb{R}$ |
| $\Psi(p) = e^{-S} \cdot e^{i\Theta}$ | Path amplitude (U(1)) | $\mathbb{C}$ |

The Pauli matrices are:

$$
\sigma_x = \begin{pmatrix} 0 & 1 \\ 1 & 0 \end{pmatrix}, \quad
\sigma_y = \begin{pmatrix} 0 & -i \\ i & 0 \end{pmatrix}, \quad
\sigma_z = \begin{pmatrix} 1 & 0 \\ 0 & -1 \end{pmatrix}
$$

They satisfy $[\sigma_i, \sigma_j] = 2i\epsilon_{ijk}\sigma_k$ and generate the Lie algebra su(2).

---

## 3. SU(2) Spinor Transport

### 3.1 Edge Transport Matrix

For a directed edge $(x \to y)$ with connection $\omega(x,y)$ and rotation axis $\hat{n}(x,y) \in \mathbb{R}^3$, $\|\hat{n}\| = 1$, define the SU(2) edge transport:

$$
U(x,y) = \exp\!\Bigl(-\frac{i\,\omega(x,y)}{2}\;\hat{n}(x,y) \cdot \vec{\sigma}\Bigr)
$$

Using the Pauli exponential identity:

$$
U(x,y) = \cos\!\Bigl(\frac{\omega}{2}\Bigr)\,I - i\sin\!\Bigl(\frac{\omega}{2}\Bigr)\;\hat{n} \cdot \vec{\sigma}
$$

**Properties:**
- $U(x,y) \in \text{SU}(2)$: determinant 1, unitary
- $U(x,y)^{-1} = U(x,y)^\dagger$
- When $\hat{n} = \hat{z}$ for all edges: $U$ is diagonal, and SU(2) reduces to U(1)

### 3.2 Path Transport

For a path $p = (x_0, x_1, \ldots, x_n)$, define the ordered path transport:

$$
U(p) = U(x_{n-1}, x_n) \cdot U(x_{n-2}, x_{n-1}) \cdots U(x_0, x_1)
$$

The ordering is right-to-left (the first edge transport is applied first to the spinor).

**Proposition 3.1.** $U(p) \in \text{SU}(2)$ for all paths $p$.

*Proof.* SU(2) is closed under matrix multiplication. Each $U(x_i, x_{i+1}) \in \text{SU}(2)$, so their ordered product is in SU(2). $\square$

**Proposition 3.2** (Non-commutativity). For edges with distinct rotation axes $\hat{n}_1 \neq \hat{n}_2$:

$$
U_1 \cdot U_2 \neq U_2 \cdot U_1 \quad\text{(generically)}
$$

*Proof.* The su(2) generators satisfy $[\sigma_i, \sigma_j] = 2i\epsilon_{ijk}\sigma_k \neq 0$ for $i \neq j$. $\square$

This is the fundamental difference from U(1): path order matters.

### 3.3 Spinor Amplitude

Define the spinor path amplitude:

$$
\Psi(p) = e^{-S(p)} \cdot U(p) \cdot |\text{ref}\rangle \in \mathbb{C}^2
$$

where $|\text{ref}\rangle \in \mathbb{C}^2$ is a fixed reference spinor (default: $|\uparrow\rangle = (1, 0)^T$).

**Proposition 3.3** (Magnitude invariance). For all paths $p$ and all axis assignments:

$$
\|\Psi(p)\| = e^{-S(p)}
$$

*Proof.* Since $U(p) \in \text{SU}(2)$ is unitary, $\|U(p) \cdot |\text{ref}\rangle\| = \||\text{ref}\rangle\| = 1$. Therefore $\|\Psi(p)\| = e^{-S(p)} \cdot 1 = e^{-S(p)}$. $\square$

This means the coherence factor is independent of the non-Abelian structure. The SU(2) phase affects only the *direction* of the spinor, not its magnitude. Individual path weights are unchanged; interference patterns are where the difference appears.

### 3.4 Spinor Superposition and Intensity

For a target state $z$ with bounded path set $\{p_1, \ldots, p_k\}$:

$$
\Psi(z) = \sum_{p \to z} \Psi(p) \in \mathbb{C}^2
$$

$$
I(z) = \|\Psi(z)\|^2 = |\Psi_1(z)|^2 + |\Psi_2(z)|^2
$$

Interference now occurs **component-wise** in ℂ². Two paths that destructively interfere in U(1) may constructively interfere in one spinor component while destructively interfering in the other, producing strictly richer interference patterns.

### 3.5 720° Periodicity

A fundamental property of SU(2) is double-covering of SO(3):

$$
U(\omega = 2\pi, \hat{n}) = -I \quad\text{(not identity)}
$$
$$
U(\omega = 4\pi, \hat{n}) = +I \quad\text{(identity)}
$$

A full $2\pi$ rotation of the connection phase does *not* return the spinor to its original state — it acquires a sign flip. Only a $4\pi$ rotation restores identity. This half-integer spin structure is inherent in SU(2) and has been verified numerically in the E₀ implementation (§6.2).

---

## 4. Geometry-Derived su(2) Connection

### 4.1 From External to Emergent Axes

Section 3 introduced the rotation axis $\hat{n}(x,y)$ as a parameter. This section shows that $\hat{n}$ can be *derived* from the local Helmholtz structure of the transition field.

The key insight: the Helmholtz decomposition of $v$ into $v_{\text{grad}}$ and $v_{\text{rot}}$ already contains three distinguishable geometric quantities on each edge, corresponding naturally to three su(2) generators.

### 4.2 Three-Component Connection

For a directed edge $(x \to y)$, define the su(2) connection vector:

$$
\vec{A}(x,y) = (A_1, A_2, A_3)
$$

where:

**$A_3$ (σ_z component): Direct connection.**
$$
A_3 = \omega(x,y)
$$

This is the existing scalar connection — the component that reduces to U(1) when the others vanish.

**$A_1$ (σ_x component): Vorticity gradient.**
$$
A_1 = \overline{\omega}_{N(x) \setminus y} - \overline{\omega}_{N(y) \setminus x}
$$

where $\overline{\omega}_{N(x) \setminus y}$ is the mean connection $\omega(x,z)$ over all outgoing neighbors $z$ of $x$, excluding $y$. Non-zero when the source and target sit in regions of different rotational intensity.

**$A_2$ (σ_y component): Face holonomy.**
$$
A_2 = \frac{1}{|T|} \sum_{z \in T} \bigl[\omega(x,y) + \omega(y,z) + \omega(z,x)\bigr]
$$

where $T$ is the set of vertices $z$ forming directed triangles $x \to y \to z \to x$ (i.e., edges $y \to z$ and $z \to x$ both exist). Non-zero when local faces carry gauge curvature — the discrete analog of the Yang-Mills field strength $F_{\mu\nu}$.

### 4.3 Geometric Transport

The total connection angle and emergent axis are:

$$
\|\vec{A}\| = \sqrt{A_1^2 + A_2^2 + A_3^2}, \qquad \hat{n} = \frac{\vec{A}}{\|\vec{A}\|}
$$

The geometric edge transport is:

$$
U_{\text{geo}}(x,y) = \exp\!\Bigl(-\frac{i}{2}\,\vec{A}(x,y) \cdot \vec{\sigma}\Bigr)
$$

**Reduction property:** When $A_1 = A_2 = 0$ (no vorticity gradient, no face holonomy), the geometric transport reduces to the minimal SU(2) embedding:

$$
U_{\text{geo}} = \exp\!\Bigl(-\frac{i}{2}\omega\,\sigma_z\Bigr)
$$

which is diagonal and equivalent to U(1).

### 4.4 Antisymmetry

Each component $A_i$ is antisymmetric:

$$
A_i(y,x) = -A_i(x,y) \quad \text{for } i = 1, 2, 3
$$

This follows from:
- $A_3$: $\omega$ is antisymmetric by construction
- $A_1$: swapping $x$ and $y$ swaps the subtraction
- $A_2$: reversing the triangle path reverses the holonomy sign

Therefore $\vec{A}(y,x) = -\vec{A}(x,y)$, and:

$$
U_{\text{geo}}(y,x) = U_{\text{geo}}(x,y)^\dagger
$$

### 4.5 Four Theories

The E₀ framework now supports four distinct phase theories, forming a hierarchy:

| Theory | Transport | Amplitude | Commutativity |
|--------|-----------|-----------|---------------|
| U(1) | $e^{i\omega}$ | $\Psi \in \mathbb{C}$ | Abelian |
| SU(2)-minimal ($\hat{n} = \hat{z}$) | $e^{-i\omega/2\,\sigma_z}$ | $\Psi \in \mathbb{C}^2$ | Abelian (diagonal) |
| SU(2)-geometric | $e^{-i\vec{A}\cdot\vec{\sigma}/2}$ | $\Psi \in \mathbb{C}^2$ | Non-Abelian |
| SU(2)-multi-axis | $e^{-i\omega/2\,\hat{n}(e)\cdot\vec{\sigma}}$ | $\Psi \in \mathbb{C}^2$ | Non-Abelian |

The first is the baseline from Papers 1–2. The second lifts it to spinors without changing interference (phase halving). The third and fourth introduce genuine non-commutativity. Numerical tests confirm all four produce distinct intensities on the same graph (§6.2).

---

## 5. Curvature and Topological Modulation

### 5.1 Edge Curvature

The $A_2$ component of the geometric connection (§4.2) measures face holonomy — the net phase around triangles through an edge. This motivates a scalar curvature measure.

**Definition 5.1** (Edge curvature). For a directed edge $(x \to y)$, define:

$$
\kappa(x,y) = \frac{1}{|T|}\sum_{z \in T} \bigl|\omega(x,y) + \omega(y,z) + \omega(z,x)\bigr|
$$

where $T$ is the set of triangle-closing vertices (as in §4.2). If $T = \emptyset$, then $\kappa = 0$.

Properties:
- $\kappa \geq 0$ (absolute value of holonomy)
- $\kappa = 0$ when all face holonomies vanish (flat geometry)
- $\kappa = 0$ when no triangles exist through the edge

### 5.2 Topological Modulation Factor

**Definition 5.2** (M_H). For a directed edge $(x \to y)$:

$$
M_H(x,y) = \frac{1}{1 + \kappa(x,y)}
$$

Properties:
- $M_H \in (0, 1]$
- $\kappa = 0 \implies M_H = 1$ (no modulation)
- $\kappa \to \infty \implies M_H \to 0$ (complete suppression)

**Alternative.** The formula $M_H = e^{-\kappa}$ has the same asymptotic limits (1 at $\kappa = 0$, 0 at $\kappa \to \infty$) but decays faster for moderate curvature. The choice between algebraic and exponential damping is an open parameter.

### 5.3 Modulated Transition Field

The transition field with curvature modulation is:

$$
v(x,y) = \Delta(x,y) \cdot M_H(x,y) \cdot \exp\!\bigl(-S_{\text{eff}}(x \to y)\bigr)
$$

This is the full form specified in [Paper 1, §5.1], where M_H was previously set to 1.

**Operational interpretation:** High-curvature edges — those surrounded by non-integrable face structure — have their transition capacity reduced. The system preferentially routes through flat (integrable) regions of the landscape.

### 5.4 Circular Dependency and Resolution

A subtlety arises: the modulated $v$ changes the Helmholtz decomposition, which changes $v_{\text{rot}}$, which changes $\omega$, which changes $\kappa$, which changes $M_H$, which changes $v$. This is a circular dependency:

$$
v \to \Phi \to v_{\text{rot}} \to \omega \to \kappa \to M_H \to v
$$

**Resolution:** M_H is computed from the *base* (unmodulated) $\omega$. The curvature $\kappa$ reflects the pure geometric structure of the landscape. M_H then modulates the transition field as a one-way correction, not an iterative fixed point.

Implementation: the `curvature_modulation` flag is temporarily disabled during M_H cache construction, ensuring that $\kappa$ is computed from the unmodulated transition field. The Helmholtz cache is invalidated before and after.

### 5.5 Curvature Feedback Loop

Although M_H is computed from base $\omega$, the modulated $v$ changes the landscape for *subsequent* controller cycles. Through historization, the feedback becomes temporal:

$$
\text{Cycle } t: \quad \kappa_t \to M_{H,t} \to v_t \to \text{transition} \to H_{t+1}
$$
$$
\text{Cycle } t{+}1: \quad R_{\text{eff},t+1} \to S_{t+1} \to v_{t+1} \to \kappa_{t+1} \to M_{H,t+1}
$$

Historization provides the temporal coupling. At any given cycle, M_H is a static modulation; across cycles, it participates in the dynamic evolution of the landscape.

### 5.6 Experimental Switch

Curvature modulation is controlled by a boolean parameter on the Landscape:

```
Landscape(curvature_modulation=False)  # default: M_H ≡ 1
Landscape(curvature_modulation=True)   # experimental: M_H from κ
```

When disabled, all existing behavior is exactly preserved. The 1082 tests from prior work pass without modification. When enabled, 35 additional tests verify the modulation behavior across four graph topologies.

---

## 6. Numerical Verification

### 6.1 Test Domains

Four graph topologies are used for systematic testing:

| Domain | Nodes | Edges | Triangles | Key Property |
|--------|-------|-------|-----------|--------------|
| **Triangle** | 3 | 6 | 2 per edge | Minimal curved topology |
| **Line** | 3 | 4 | 0 | Flat (no triangles) |
| **Diamond** | 4 | 12+ | Variable | Mixed curvature |
| **Tetrahedron** | 4 | 12 | 2 per edge | Fully connected, uniformly curved |

All domains use strongly asymmetric edge parameters (forward: $\Delta = 5.0$, $R_0 = 0.1$; reverse: $\Delta = 0.1$, $R_0 = 0.9$) to produce non-zero $\omega$ via the Helmholtz decomposition. Symmetric edges yield $\omega = 0$ (the rotational component vanishes when forward and reverse have identical parameters), making all gauge structure trivially zero.

### 6.2 B1 Results: Per-Edge SU(2) Axes (36 Tests)

**Non-commutativity (4 tests).** All three Pauli pairs $(\sigma_x, \sigma_y)$, $(\sigma_y, \sigma_z)$, $(\sigma_x, \sigma_z)$ produce $\|AB - BA\| > 0.1$ for typical E₀ connection angles. Same-axis products commute to machine precision ($< 10^{-12}$).

**Path-order dependence (4 tests).** On the tetrahedron with orthogonal per-edge axes, the paths $A \to B \to C$ and $A \to C \to B$ produce transport matrices differing by $\|U_1 - U_2\| > 0.01$. Under single-axis (σ_z), the difference is $< 0.06$.

**Holonomy (4 tests).** Triangle $A \to B \to C \to A$ with multi-axis assignment: distance-to-identity $= 0.92$. Same triangle with single-axis: $0.05$. Different triangles produce different holonomies (difference $= 1.19$). Orientation reversal changes the holonomy.

**Multi-axis interference (4 tests).** On the tetrahedron 3-path family: multi-axis intensity $I = 1.04$, single-axis $I = 0.82$ (difference $= 0.23$). Single-path families show identical intensity under any axis assignment (verified to 10 decimal places) — a critical control.

**Four-theory comparison (1 test).** On the tetrahedron, all four theories (U(1), SU(2)-σ_z, SU(2)-geometric, SU(2)-multi-axis) produce distinct intensities.

**Controller integration (5 tests).** The `axis_fn` parameter threads through `E0Controller → _compute_overlay → analyze_controller_state → spinor_psi`. On a fan graph (action M has 2 paths), multi-axis produces overlay intensity differing from single-axis by 0.015. With `axis_fn=None`, results are identical to prior behavior (10 decimal places).

### 6.3 B2 Results: Curvature Modulation (35 Tests)

**Flat geometry (5 tests).** Line graph: $\kappa = 0$ for all edges, $M_H = 1$, $v$ unchanged by modulation. Symmetric triangle: $\omega = 0$, same result. These are negative controls confirming that modulation is a no-op on flat topologies.

**Curved geometry (6 tests).** Asymmetric triangle: $\kappa > 0$, $M_H < 1$, $v_{\text{mod}} < v_{\text{base}}$. Tetrahedron: all edges curved, producing differential modulation.

**Formula verification (3 tests).** $v_{\text{mod}} / v_{\text{base}} = M_H$ verified to 8 decimal places for all edges. Manual formula $v = \Delta \cdot M_H \cdot C(S_{\text{eff}})$ verified to 12 decimal places.

**Downstream propagation (3 tests).** Curvature modulation changes $v_{\text{rot}}$, $\omega$, and holonomy on the diamond graph. Helmholtz potential $\Phi$ differs between modulated and unmodulated regimes.

**Admissibility invariance (1 test).** `admissible_neighbors(x)` returns the same set with or without modulation — M_H only scales $v$, never removes edges.

**Cache consistency (3 tests).** M_H cache is built once and reused. Entries exist for all edges. Helmholtz cache key includes the modulation flag.

### 6.4 Topology Reclassification Under SU(2)

A significant operational consequence of SU(2) transport is topology reclassification. On Gordian-lite graphs (multi-path families with near-destructive interference under U(1)):

| Topology | U(1) Override Rate | SU(2) Override Rate | Mechanism |
|----------|-------------------|--------------------:|-----------|
| Triangle | 0% | 0% | Single family — no interference |
| Diamond | ~50% | ~50% | Single path per family — no phase effect |
| Gordian-lite | ~90% | ~0% | Phase halving eliminates destructive interference |

The Gordian-lite reclassification is the most dramatic: under U(1), A-family's two paths destructively interfere (near-cancellation), making the overlay strongly prefer B-family. Under SU(2), the phase is halved ($\omega \to \omega/2$), weakening the destructive interference sufficiently that overlay and greedy agree.

On G5 multi-goal domains, the winner flips: U(1) selects goal B (A-family destructively interferes, $I = 0.024$); SU(2) selects goal A (halved phase restores coherence, $I = 1.028$), a 43× intensity increase.

---

## 7. Discussion

### 7.1 What is Derived vs. Assumed

The SU(2) structure rests on two assumptions beyond the E₀ core:

1. **The spinor representation:** Promoting scalar amplitudes to ℂ² is a choice, not a derivation. The mathematical justification is that SU(2) is the universal cover of SO(3), and the connection $\omega$ already generates rotations.

2. **The curvature formula:** $M_H = 1/(1+\kappa)$ is a candidate, not a uniquely determined form. It satisfies the required boundary conditions ($M_H = 1$ for flat, $M_H \to 0$ for strongly curved) and has the simplest algebraic form, but $M_H = e^{-\kappa}$ is equally valid.

Everything else follows from the existing E₀ chain. The three-component connection $\vec{A}$ is derived from the Helmholtz decomposition. The edge curvature $\kappa$ is computed from face holonomies already present in the framework. No new primitives are introduced.

### 7.2 Relation to Gauge Theory

The geometric connection $\vec{A}(x,y)$ has structural parallels to Yang-Mills theory:

- $A_3$ (direct connection) corresponds to the gauge potential $A_\mu$
- $A_2$ (face holonomy) corresponds to the field strength $F_{\mu\nu}$
- $\kappa$ (mean $|F|$) corresponds to the action density

These are *analogs*, not identifications. E₀ operates on discrete directed graphs, not smooth manifolds. The Helmholtz decomposition replaces the de Rham decomposition; the graph Laplacian replaces the Hodge Laplacian. The correspondence is structural, not physical.

### 7.3 Backward Compatibility

The design is strictly backward-compatible:

- `axis_fn=None` reduces to $\hat{n} = \hat{z}$, which reduces SU(2) to U(1) phase structure
- `curvature_modulation=False` (default) gives $M_H = 1$, recovering the existing transition field
- All 1082 prior tests pass without modification
- The 71 new tests cover the extended regime

The experimental switch approach allows the modulated and unmodulated regimes to coexist and be compared on identical domains.

### 7.4 Open Questions

1. **Self-consistency of iterated M_H.** The current implementation computes $\kappa$ from base $\omega$, not from modulated $\omega$. A fixed-point iteration $\kappa_{n+1} = \kappa(\omega_{\text{mod},n})$ could be studied for convergence.

2. **Physical interpretation.** Does the curvature feedback have a natural interpretation in terms of "structural learning difficulty"? High-curvature regions might correspond to areas of the landscape where historization produces inconsistent signals.

3. **Scaling.** The face-finding step in $\kappa$ computation is $O(|E|)$ per edge. For large graphs, approximate curvature measures may be needed.

4. **Canonical status.** The canon [e0-canonical-reference.txt] does not address non-Abelian structure. The B1–B2 extensions are research extensions, not canonical components. A future canon revision would need to either incorporate or explicitly exclude them.

---

## 8. Conclusion

Starting from the E₀ transition framework and its Abelian U(1) connection, we have shown that non-Abelian SU(2) structure emerges naturally at three levels:

1. **Algebraic:** Per-edge rotation axes produce non-commutative transport and path-order-dependent spinor amplitudes.

2. **Geometric:** The Helmholtz decomposition of the transition field yields a three-component su(2) connection with intrinsic meaning — direct phase, vorticity gradient, and face curvature.

3. **Topological:** Face holonomy defines an edge curvature that modulates the transition field, closing a feedback loop between geometry and dynamics.

The resulting framework preserves all prior E₀ behavior when the extensions are disabled, produces measurably different interference patterns when enabled, and is verified by 71 tests across four graph topologies. No new primitives are introduced: the non-Abelian structure is latent in the existing dependency chain

$$
\Delta \to R_0 \to H \to R_{\text{eff}} \to S \to v \to v_{\text{rot}} \to \omega \to \vec{A} \to U \to \Psi \in \mathbb{C}^2
$$

and is revealed by lifting the representation from scalars to spinors.

---

## Appendix A: Implementation Reference

### A.1 Core Functions

| Function | Module | Purpose |
|----------|--------|---------|
| `pauli_exponential(angle, axis)` | `spinor_connection.py` | $U = e^{-i\alpha/2\,\hat{n}\cdot\vec{\sigma}}$ |
| `su2_edge_transport(L, x, y, axis)` | `spinor_connection.py` | Single-edge SU(2) transport |
| `su2_path_transport(L, path, axis_fn)` | `spinor_connection.py` | Ordered path transport $U(p)$ |
| `su2_connection(L, x, y)` | `spinor_connection.py` | $\vec{A}(x,y) = (A_1, A_2, A_3)$ |
| `su2_geometric_transport(L, x, y)` | `spinor_connection.py` | $U_{\text{geo}} = e^{-i\vec{A}\cdot\vec{\sigma}/2}$ |
| `spinor_psi(L, path, ref, axis_fn)` | `spinor_connection.py` | $\Psi(p) = e^{-S}\cdot U(p)\cdot|\text{ref}\rangle$ |
| `spinor_sum_paths(L, paths, ref, axis_fn)` | `spinor_connection.py` | $\Psi(z) = \sum \Psi(p)$ |
| `spinor_intensity(L, paths, ref, axis_fn)` | `spinor_connection.py` | $I(z) = \|\Psi(z)\|^2$ |
| `edge_curvature(L, x, y)` | `connection.py` | $\kappa(x,y)$ |
| `M_H_factor(L, x, y)` | `connection.py` | $M_H = 1/(1+\kappa)$ |
| `Landscape.transition_field(x, y)` | `landscape.py` | $v = \Delta \cdot M_H \cdot e^{-S}$ |

### A.2 Test Suites

| Suite | Tests | Module |
|-------|------:|--------|
| B1: Multi-Axis SU(2) | 36 | `test_multi_axis_su2.py` |
| B2: Curvature Modulation | 35 | `test_curvature_modulation.py` |
| SU(2) Reclassification | 21 | `test_topology_classification.py`, `test_g5_edge_cases.py`, `test_born_sampling.py` |
| SU(2) Core | 52 | `test_spinor.py` |
| **Total SU(2)-related** | **144** | |

### A.3 Reproducibility

```bash
# Full regression (1117 tests, 0 failures, 32 skipped)
python -m unittest discover -s e0_controller -p "test_*.py" -v

# B1 only (36 tests)
python -m unittest e0_controller.test_multi_axis_su2 -v

# B2 only (35 tests)
python -m unittest e0_controller.test_curvature_modulation -v
```

---

## Appendix B: Derived/Empirical/Heuristic Classification

| Component | Classification | Justification |
|-----------|---------------|---------------|
| $U(x,y) = e^{-i\omega/2\,\hat{n}\cdot\vec{\sigma}}$ | **Derived** | Standard Lie algebra exponential map |
| $U(p) \in \text{SU}(2)$ | **Derived** | Group closure under multiplication |
| $\|\Psi(p)\| = e^{-S(p)}$ | **Derived** | Unitarity of SU(2) |
| $\vec{A} = (A_1, A_2, A_3)$ | **Derived** | Helmholtz decomposition applied to graph |
| $\kappa(x,y)$ | **Derived** | Defined from existing holonomy |
| $M_H = 1/(1+\kappa)$ | **Heuristic** | Candidate satisfying boundary conditions |
| $\hat{n} = \hat{z}$ default | **Convention** | Simplest embedding; backward-compatible |
| Per-edge axis_fn | **Extension** | Degree of freedom; not uniquely determined |
| 720° periodicity | **Derived** | Consequence of $\text{SU}(2) \to \text{SO}(3)$ double cover |

---

_End of Paper 3 Draft v1.0_
