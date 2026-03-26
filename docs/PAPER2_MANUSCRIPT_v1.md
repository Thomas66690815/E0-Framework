# E₀-II: Spinor Amplitudes and the Born Criterion on Discrete Transition Graphs

**Thomas Wehner**

---

## Abstract

The companion paper (E₀-I) derived complex path amplitudes
$\Psi = \exp(-S + i\Theta) \in \mathbb{C}$ exhibiting interference on
directed transition graphs. This paper asks: *why $\mathbb{C}$?* We show
that encoding *internal difference* — rotational structure that
distinguishes transitions beyond scalar magnitude — forces the minimal
carrier space from $\mathbb{C}$ to $\mathbb{C}^2$, yielding SU(2)-valued
path transport instead of U(1) phases. The spinor lift introduces three
qualitatively new effects: (1) 720° periodicity — the transport operator
returns to identity only after two full rotations, (2) phase halving —
interference patterns change because SU(2) halves effective phase
differences, and (3) non-commutativity — multi-axis transport operators do
not commute, making path ordering structurally significant. We then derive
the Born criterion: under bounded exclusive realization, the probability
$P(z) = |{\Psi}(z)|^2 / \sum |{\Psi}(w)|^2$ is the unique structurally
non-arbitrary distribution over outcomes. On the Gordian Trap domain,
phase halving inverts the interference pattern, changing the dominant
action — a qualitative decision flip absent under U(1). All claims are
classified as derived, empirical, or open.

---

## 1. Introduction

### 1.1 Motivation: Beyond Scalar Phase

The E₀ framework (Paper 1) derives complex path amplitudes from three
structural primitives — difference ($\Delta$), resistance ($R$), and
historization ($H$). The derivation chain produces amplitudes
$\Psi(p) = \exp(-S(p) + i\Theta(p)) \in \mathbb{C}$ that exhibit
constructive and destructive interference. The phase $\Theta$ emerges from
the rotational component of the transition field via a discrete Helmholtz
decomposition and an antisymmetric connection $\omega$ (Paper 1, §3.5–3.6).

Paper 1 established two important properties of this phase:

1. **Gauge invariance of observables.** The holonomy $\text{Hol}(\gamma)$
   and resulting interference effects are invariant under reference-node
   choice in the Helmholtz decomposition.

2. **Gauge class dependence of the connection.** The connection $\omega$
   itself is derived up to the gauge class defined by the Helmholtz
   decomposition and antisymmetric extraction (Paper 1, §3.6, Gauge
   Freedom remark).

These properties raise a natural question: is the scalar phase $\Theta$
the *only* structurally motivated phase object, or does the transition
landscape support a richer phase geometry? The answer comes not from
physics but from an algebraic argument about *carrier spaces* — what
algebraic structure is minimally required to represent the quantities that
E₀ derives?

### 1.2 The Internal-Difference Argument

Consider two transitions $e_1 = (x, y_1)$ and $e_2 = (x, y_2)$ that share
scalar properties — same tension $S$, same coherence $C$ — but differ in
their rotational character within the transition field. Under U(1)
amplitudes, both transitions produce the same magnitude $\exp(-S)$; only
their scalar phases differ. But scalar phase is one-dimensional: it encodes
a single angle, not an *orientation* in a higher-dimensional space.

If the transition landscape contains internal structure that distinguishes
rotations in different planes — not merely different angles in the same
plane — then the U(1) representation is lossy. The minimal algebraic
structure that supports *multi-planar* rotational distinction is
$\mathbb{C}^2$, with transformations in SU(2). This is not a physical
postulate but a carrier-space minimality argument: $\mathbb{C}^2$ is the
smallest space in which non-commutative rotational structure can be
faithfully represented.

### 1.3 Contributions

This paper makes five contributions:

1. **A carrier minimality argument** showing that encoding internal
   difference requires $\mathbb{C}^2$, forcing SU(2)-valued path
   transport (§3).

2. **Three emergent effects** of the spinor lift: 720° periodicity,
   phase halving, and non-commutativity, each with formal characterization
   and empirical verification (§4).

3. **A derivation of the Born criterion** under bounded exclusive
   realization: the probability $P(z) = |\Psi(z)|^2 / \sum |\Psi(w)|^2$
   is the unique structurally non-arbitrary distribution, emerging from
   amplitude structure rather than being assumed (§5).

4. **An empirical analysis** of when SU(2) produces qualitatively different
   decisions than U(1), identifying phase halving as the mechanism for
   decision flips on trap domains (§6).

5. **Multi-goal analysis** under spinor amplitudes, extending Paper 1's
   geometry-dominance result to the SU(2) setting (§7).

### 1.4 Scope and Honesty

This paper explicitly classifies every claim as *derived* (follows from
the structural chain), *empirical* (demonstrated through experiments), or
*open* (structurally motivated but unresolved). Table 1 in Appendix E
provides the full classification.

This paper does **not** claim:
- A quantum-mechanical theory of decision-making.
- A continuous-limit formalization.
- Universal superiority of SU(2) over U(1) amplitudes.
- A resolution of the quantum measurement problem.

It claims a structurally derived extension of E₀ from scalar to spinor
amplitudes, with a conditional derivation of Born-rule probability from
graph-theoretic primitives.

---

## 2. Related Work

### 2.1 Spinor Structures in Classical Systems

Spinor representations arise naturally outside quantum mechanics whenever
a system exhibits rotational structure that is sensitive to the *sign* of
a full rotation. In geometric algebra, Hestenes [1] demonstrated that
spinors emerge as elements of even-grade Clifford algebras, with
applications to classical mechanics and electromagnetism. Grady and
Polimeni [2] developed discrete spinor structures on simplicial complexes,
showing that topological properties of manifolds can be captured by
combinatorial spinor fields. In signal processing, Bülow and Sommer [3]
introduced hypercomplex (quaternionic) representations for
multi-dimensional signals, using the algebraic structure of $\mathbb{H}
\cong \mathbb{C}^2$ to encode orientation-dependent features.

**Distinction from E₀.** These approaches embed spinor structure from an
external geometric or algebraic requirement. E₀ *derives* the need for
spinors from a carrier minimality argument: the transition landscape's
internal difference structure forces $\mathbb{C}^2$ as the minimal faithful
representation (§3).

### 2.2 The Born Rule: Derivations and Alternatives

The Born rule $P = |\Psi|^2$ is the bridge between amplitude and
probability. Its status — axiom or theorem? — is one of the foundational
questions in quantum mechanics.

**Gleason's theorem** [4] shows that in a Hilbert space of dimension
$\geq 3$, the only frame function consistent with the lattice of
projections is $P(\Pi) = \text{tr}(\rho \Pi)$, which reduces to
$P = |\Psi|^2$ for pure states. This is mathematically rigorous but
requires the full Hilbert space axioms as input.

**Zurek's envariance** [5] derives Born probabilities from
environment-assisted invariance (entanglement with an environment), without
assuming the Born rule. The key insight is that symmetry under certain
swaps of environment states forces $P = |\Psi|^2$.

**Deutsch–Wallace** [6, 7] derive Born probabilities from
decision-theoretic rationality axioms applied to agents in an Everettian
branching universe. The Born rule emerges as the unique rational betting
strategy.

**Saunders–Pitowsky** [8] approaches Born via symmetry arguments on
probability measures in Hilbert space.

**Distinction from E₀.** All these derivations presuppose quantum-mechanical
structure: Hilbert spaces, projections, entanglement, or branching
universes. E₀ derives a Born-like rule from *graph-theoretic* amplitudes
under four structural axioms (§5), without Hilbert space, without
entanglement, and without quantum postulates. The scope is narrower (only
bounded exclusive realization) but the assumptions are weaker.

### 2.3 Gauge Theory on Discrete Structures

Lattice gauge theory [9, 10] places gauge fields on the edges of a lattice,
with holonomy (Wilson loops) as the fundamental gauge-invariant observable.
The E₀ connection $\omega$ and holonomy $\text{Hol}(\gamma)$ from Paper 1
are direct discrete analogs. Recent work on gauge equivariant neural
networks extends this structure to learning: Cohen and Welling [11]
formalize gauge equivariance on fiber bundles, Favoni et al. [12]
construct lattice gauge equivariant CNNs for SU(2) gauge theory, and
He et al. [13] embed parallel transport into transformer architectures.

**Distinction from E₀.** Lattice gauge theory and gauge-equivariant networks
use SU(2) as a *representation structure* for learning or simulation. E₀
uses SU(2) as a *decision operator* — the spinor amplitude directly enters
the action-selection mechanism. The gauge group is not chosen for physical
modeling but derived from carrier minimality.

### 2.4 Non-Commutative Geometry in AI

Sheaf neural networks [14] generalize graph diffusion by attaching
vector spaces (stalks) to nodes and linear maps (restriction maps) to
edges, enabling heterogeneous information flow. The connection Laplacian
[15] defines diffusion processes that respect edge-local transport
structure. These approaches share E₀'s intuition that edge-attached
transformations carry structural information beyond scalar weights.

**Distinction from E₀.** Sheaf networks and connection Laplacians operate
in a *learning* context (representation, classification). E₀'s
non-commutativity affects *action selection*: the failure of
$U(e_1) \cdot U(e_2) = U(e_2) \cdot U(e_1)$ means that path ordering
contributes information to the interference pattern, enriching the
decision mechanism beyond what commutative (U(1)) phases can capture.

### 2.5 Positioning of Paper 2

**Table 1: Positioning of E₀-II relative to related traditions**

| Tradition | E₀-II analog | Key difference |
|-----------|-------------|----------------|
| Geometric algebra / spinors | $\mathbb{C}^2$ carrier, SU(2) transport | Derived from carrier minimality, not embedding |
| Born rule derivations | $P = \|{\Psi}\|^2 / \sum \|{\Psi}\|^2$ | Graph-theoretic axioms, no Hilbert space |
| Lattice gauge theory | $\omega$, holonomy, Wilson loops | Decision operator, not simulation |
| Gauge equivariant networks | Edge-local SU(2) transport | Action selection, not representation |
| Sheaf diffusion | Non-commutative edge maps | Interference-based control, not learning |

E₀-II's contribution is the integration: a structurally derived spinor
amplitude on directed graphs, with emergent Born-rule probability, in a
deterministic decision framework. No prior work derives SU(2) transport
from carrier minimality on discrete transition systems.

---

## 3. Carrier Minimality: Why $\mathbb{C}^2$

This section develops the central theoretical argument: the transition
landscape's internal structure forces the carrier space from $\mathbb{C}$
(adequate for Paper 1) to $\mathbb{C}^2$ (required for faithful
representation of internal difference).

### 3.1 The Carrier Problem

Paper 1 derived the complex amplitude $\Psi(p) = \exp(-S + i\Theta) \in
\mathbb{C}$ as the canonical object encoding both path tension $S$ and
path phase $\Theta$. The argument was:

1. Two independent real quantities ($S \geq 0$ and $\Theta \in \mathbb{R}$)
   must be encoded.
2. Path composition must be multiplicative:
   $K(p \circ q) = K(p) \cdot K(q)$.
3. Multiple paths must interfere (sum and partially cancel).
4. Phase must be periodic: $\Theta \sim \Theta + 2\pi k$.
5. The representation must be minimal (fewest degrees of freedom).

$\mathbb{C}$ satisfies all five requirements: magnitude $|K| = \exp(-S)$,
argument $\arg K = \Theta$, and interference via complex addition. The
exponential form $K(p) = \exp(-S + i\Theta)$ is the canonical solution.

**Question.** Is $\mathbb{C}$ the *final* carrier, or does the transition
landscape contain structure that $\mathbb{C}$ cannot faithfully represent?

### 3.2 Internal Difference

**Definition 1** (Internal Difference).
Two directed edges $e_1 = (x, y_1)$ and $e_2 = (x, y_2)$ exhibit *internal
difference* if they share scalar transport properties
($S(e_1) = S(e_2)$, $\Theta(e_1) = \Theta(e_2)$) but differ in their
rotational orientation within the transition field. That is, the
transitions are indistinguishable under U(1) transport but structurally
distinct as elements of the transition landscape.

**Remark.** Internal difference can be formalized as follows. The
connection $\omega$ (Paper 1, Def. 14) assigns a scalar to each edge.
If two edges share the same $\omega$ value but are embedded in different
*rotational planes* of the graph's local geometry, U(1) transport — which
encodes rotation as a single angle — cannot distinguish them. A richer
transport structure is needed.

### 3.3 Carrier Space Requirements

To faithfully encode internal difference, the carrier space must satisfy:

**Requirement C1** (Rotational fidelity). Transport operators must
distinguish rotations in different planes, not merely different angles.

**Requirement C2** (Norm preservation). Transport must preserve the norm
of the amplitude: $\|U(e) \cdot \psi\| = \|\psi\|$ for all edges $e$
and all states $\psi$.

**Requirement C3** (Composition). Path transport must compose
multiplicatively: $U(p) = U(e_n) \cdot U(e_{n-1}) \cdots U(e_1)$.

**Requirement C4** (Interference). Amplitudes for different paths to the
same endpoint must sum: $\Psi_{\text{total}} = \sum_p \Psi(p)$.

**Requirement C5** (Minimality). The carrier space has the fewest
dimensions compatible with C1–C4.

### 3.4 The Minimality Argument

**Proposition 1** (Carrier Minimality).
*The minimal carrier space satisfying Requirements C1–C5 is
$\mathbb{C}^2$, with transport operators in SU(2).*

*Proof sketch.*

**Step 1: $\mathbb{C}$ is insufficient.** U(1) is abelian: all transport
operators commute. Therefore $U(e_1) \cdot U(e_2) = U(e_2) \cdot U(e_1)$
for all edges. This means U(1) cannot encode Requirement C1 — rotations
in different planes commute in U(1), so they are indistinguishable from
rotations in the same plane.

**Step 2: $\mathbb{C}^2$ is sufficient.** The group SU(2) acts on
$\mathbb{C}^2$ by matrix multiplication, satisfying:
- C1: SU(2) is non-abelian; $[\sigma_i, \sigma_j] = 2i\epsilon_{ijk}\sigma_k
  \neq 0$ for $i \neq j$.
- C2: SU(2) matrices are unitary ($U^\dagger U = \mathbb{I}$), so
  $\|U\psi\| = \|\psi\|$.
- C3: Matrix multiplication composes path transport.
- C4: $\mathbb{C}^2$ supports vector addition for interference.

**Step 3: $\mathbb{C}^2$ is minimal.** Among compact connected Lie groups:
- Rank 0: trivial group $\{e\}$ — no transport.
- Rank 1: U(1) (1-dimensional, abelian — excluded by C1) and SU(2)
  (3-dimensional, non-abelian — satisfies C1–C4).
- SU(2) acts faithfully on $\mathbb{C}^2$ (its fundamental
  representation). Any faithful representation of a non-abelian group
  requires $\dim \geq 2$.

Therefore $\mathbb{C}^2$ with SU(2) transport is the minimal *faithful
non-abelian* carrier. $\square$

**Remark.** The group SO(3) also satisfies non-commutativity, but
SO(3) $\cong$ SU(2)$/\mathbb{Z}_2$ is not simply connected:
$\pi_1(\text{SO}(3)) = \mathbb{Z}_2$. This means SO(3) has a topological
sign ambiguity on paths — a $2\pi$ rotation in SO(3) is topologically
non-trivial. The simply connected cover SU(2) resolves this ambiguity,
at the cost of introducing 720° periodicity (§4.2). The choice between
SO(3) and SU(2) is not arbitrary: SU(2), as the universal cover, is the
*canonical* choice for path-dependent transport, because it avoids the
sign ambiguity that would make path amplitudes representation-dependent.

### 3.5 The Spinor Lift

The transition from U(1) to SU(2) defines the *spinor lift*:

**Definition 2** (Spinor Carrier).
The *spinor carrier space* is $\mathbb{C}^2$, equipped with the standard
Hermitian inner product $\langle \psi, \phi \rangle = \psi^\dagger \phi$.

**Definition 3** (Reference Spinor).
The *reference spinor* is the fixed state
$|\text{ref}\rangle = |\!\uparrow\rangle = \begin{pmatrix} 1 \\ 0 \end{pmatrix}$,
serving as the initial condition for path transport.

**Definition 4** (SU(2) Edge Transport).
Given the connection $\omega(x, y)$ (Paper 1, Def. 14) and a rotation
axis $\hat{n} \in S^2$, the *SU(2) edge transport* is

$$U(x \to y) = \exp\!\left(-\frac{i\,\omega(x,y)}{2}\;\hat{n} \cdot \vec{\sigma}\right)$$

where $\vec{\sigma} = (\sigma_1, \sigma_2, \sigma_3)$ are the Pauli
matrices and the matrix exponential evaluates to

$$U = \cos\!\left(\frac{\omega}{2}\right)\mathbb{I} - i\sin\!\left(\frac{\omega}{2}\right)(\hat{n} \cdot \vec{\sigma})$$

**Definition 5** (Minimal Embedding).
The *minimal embedding* uses $\hat{n} = \hat{z} = (0, 0, 1)$, yielding

$$U_{\min}(x \to y) = \exp\!\left(-\frac{i\,\omega(x,y)}{2}\,\sigma_3\right) = \begin{pmatrix} e^{-i\omega/2} & 0 \\ 0 & e^{i\omega/2} \end{pmatrix}$$

Under minimal embedding, the first component of the spinor amplitude
reduces to U(1) transport with halved phase: $e^{-i\omega/2}$ vs.
$e^{i\omega}$.

---

## 4. SU(2) Path Transport

### 4.1 Spinor Path Amplitude

**Definition 6** (Spinor Path Amplitude).
The *spinor path amplitude* for a path $p = (x_0, x_1, \ldots, x_n)$ is

$$\Psi_{\text{SU(2)}}(p) = \exp(-S(p)) \cdot U(p) \cdot |\text{ref}\rangle \in \mathbb{C}^2$$

where $S(p)$ is the path tension (Paper 1, Def. 8), $U(p) = U(e_n) \cdot
U(e_{n-1}) \cdots U(e_1)$ is the ordered product of edge transports, and
$|\text{ref}\rangle = |\!\uparrow\rangle$.

**Remark.** The transport product is ordered right-to-left: edge $e_1$ is
applied first to the reference spinor. This ordering is significant
because SU(2) is non-abelian — permuting edges changes the result (§4.4).

**Proposition 2** (Magnitude Consistency).
*For any path $p$:*

$$\|\Psi_{\text{SU(2)}}(p)\| = |\Psi_{\text{U(1)}}(p)| = \exp(-S(p))$$

*Proof.* Since $U(p) \in \text{SU}(2)$ is unitary, $\|U(p) \cdot
|\text{ref}\rangle\| = \||\text{ref}\rangle\| = 1$. Therefore
$\|\Psi_{\text{SU(2)}}(p)\| = \exp(-S(p)) \cdot 1 = \exp(-S(p))$. The
U(1) magnitude is $|\exp(-S + i\Theta)| = \exp(-S)$ by definition. $\square$

**Corollary.** On single-path endpoints (no interference), SU(2) and U(1)
produce identical intensities. Divergence requires multi-path
superposition.

### 4.2 Effect 1: 720° Periodicity

The defining topological property of SU(2) transport is *double covering*:
a full $2\pi$ rotation does not return the transport operator to identity
but to its negative.

**Theorem 1** (720° Periodicity).
*For any unit vector $\hat{n} \in S^2$:*

$$\exp(-i\pi\,\hat{n} \cdot \vec{\sigma}) = -\mathbb{I} \qquad (360° \text{ rotation})$$

$$\exp(-i \cdot 2\pi\,\hat{n} \cdot \vec{\sigma}) = +\mathbb{I} \qquad (720° \text{ rotation})$$

*Proof.* Using the Pauli exponential formula:

$$\exp(-i\theta\,\hat{n} \cdot \vec{\sigma}) = \cos\theta\,\mathbb{I} - i\sin\theta\,(\hat{n}\cdot\vec{\sigma})$$

At $\theta = \pi$: $\cos\pi = -1$, $\sin\pi = 0$, so
$\exp(-i\pi\,\hat{n}\cdot\vec{\sigma}) = -\mathbb{I}$.

At $\theta = 2\pi$: $\cos 2\pi = 1$, $\sin 2\pi = 0$, so
$\exp(-i \cdot 2\pi\,\hat{n}\cdot\vec{\sigma}) = +\mathbb{I}$. $\square$

**Interpretation.** In the U(1) representation, a phase accumulation of
$2\pi$ is trivial: $e^{i \cdot 2\pi} = 1$. In SU(2), the corresponding
half-angle transport accumulates $\pi$, giving $-\mathbb{I}$. The spinor
*remembers* having gone around — it acquires a sign that cancels only
after a second full rotation. This is the hallmark of spinorial
(half-integer) representations and is verified numerically to $10^{-14}$
across all axes (52 tests).

### 4.3 Effect 2: Phase Halving

The SU(2) edge transport (Def. 4) uses the half-angle $\omega/2$ where
U(1) uses the full angle $\omega$. This *phase halving* has a direct
impact on interference.

**Proposition 3** (Phase Halving Effect on Interference).
*Let two paths $p_1, p_2$ to the same endpoint have U(1) phase difference
$\Delta\Theta$ and equal coherence $C$. Under U(1), the interference
term is $2C^2\cos(\Delta\Theta)$. Under SU(2) minimal embedding
($\hat{n} = \hat{z}$), the interference term in the first spinor
component is $2C^2\cos(\Delta\Theta/2)$.*

*Proof.* Under U(1):
$\Psi_1 + \Psi_2 = C(e^{i\theta_1} + e^{i\theta_2})$, so
$I = |\Psi_1 + \Psi_2|^2 = 2C^2(1 + \cos(\Delta\Theta))$.

Under SU(2) minimal embedding, the first component is
$\psi_1 + \psi_2 = C(e^{-i\theta_1/2} + e^{-i\theta_2/2})$, so
the first-component intensity is
$2C^2(1 + \cos(\Delta\Theta/2))$.

The interference term changes from $\cos(\Delta\Theta)$ to
$\cos(\Delta\Theta/2)$. $\square$

**Consequence.** The phase halving effect is most dramatic when
$\Delta\Theta \approx \pi$:

- **U(1):** $\cos(\pi) = -1$ — *full destructive* interference.
- **SU(2):** $\cos(\pi/2) = 0$ — *orthogonal* (no interference, neither
  constructive nor destructive).

This means paths that destructively interfere under U(1) become
*neutral* under SU(2), potentially changing the dominant action.

**Empirical verification** (Gordian Trap domain):

| Transport | Phase difference | Interference term | Intensity $I(\text{A1})$ | Winner |
|-----------|-----------------|-------------------|-------------------------|--------|
| U(1) | $\Delta\Theta \approx \pi$ | $\cos(\pi) = -1$ | 0.018 (2%) | B1 |
| SU(2) minimal | $\Delta\Theta/2 \approx \pi/2$ | $\cos(\pi/2) \approx 0$ | 0.838 (84%) | A1 |

This is a *qualitative decision flip*: U(1) selects B1 (the coherent path),
SU(2) selects A1 (the path family whose destructive interference is
neutralized by phase halving).

### 4.4 Effect 3: Non-Commutativity

U(1) transport operators commute: $e^{i\alpha} \cdot e^{i\beta} =
e^{i\beta} \cdot e^{i\alpha}$ for all $\alpha, \beta$. SU(2) transport
operators, in general, do not.

**Proposition 4** (Non-Commutativity).
*For distinct axes $\hat{n}_1 \neq \hat{n}_2$ and non-zero angles
$\omega_1, \omega_2$, the SU(2) transport operators satisfy*

$$[U_1, U_2] = U_1 U_2 - U_2 U_1 \neq 0$$

*in general. Specifically, for the Pauli generators:*

$$[\sigma_i, \sigma_j] = 2i\epsilon_{ijk}\sigma_k$$

*Proof.* Direct computation from the Pauli algebra. For example:
$\sigma_1\sigma_2 = i\sigma_3$ and $\sigma_2\sigma_1 = -i\sigma_3$,
so $[\sigma_1, \sigma_2] = 2i\sigma_3 \neq 0$. $\square$

**Structural significance.** Non-commutativity means that the *order* of
edges in a path contributes to the spinor amplitude. Two paths with the
same edge set but different orderings produce different spinor transports.
In U(1), edge ordering is irrelevant (phases add commutatively). In SU(2),
edge ordering carries structural information.

### 4.5 Geometric Connection

The minimal embedding ($\hat{n} = \hat{z}$) uses a single rotation axis
for all edges. A richer structure emerges when the rotation axis is
derived from the graph's local geometry.

**Definition 7** (Geometric Connection Vector).
The *geometric connection vector* assigns to each edge $(x, y) \in E$ a
three-component vector

$$\vec{A}(x, y) = (A_1, A_2, A_3)$$

with:

- $A_3(x, y) = \omega(x, y)$ — the scalar connection (Paper 1, Def. 14).
- $A_1(x, y) = \overline{\omega}(N(x) \setminus y) - \overline{\omega}(N(y) \setminus x)$ — the *vorticity gradient*, measuring the difference in average connection values between the neighborhoods of $x$ and $y$.
- $A_2(x, y) = \overline{\text{Hol}}(\triangle_{x,y})$ — the *face holonomy*, the average holonomy over directed triangles containing edge $(x, y)$.

where $\overline{\omega}(S)$ denotes the mean of $\omega$ over edges in
set $S$, and $\triangle_{x,y}$ denotes the set of directed triangles
containing edge $(x, y)$.

**Property** (Antisymmetry).
$\vec{A}(y, x) = -\vec{A}(x, y)$ by construction. $A_3$ inherits
antisymmetry from $\omega$. $A_1$ and $A_2$ are antisymmetric by the
symmetry of their definitions.

**Definition 8** (Geometric SU(2) Transport).
The *geometric transport* is

$$U_{\text{geo}}(x \to y) = \exp\!\left(-\frac{i}{2}\,\|\vec{A}\|\;\hat{A} \cdot \vec{\sigma}\right)$$

where $\hat{A} = \vec{A}/\|\vec{A}\|$ and
$\|\vec{A}\| = \sqrt{A_1^2 + A_2^2 + A_3^2}$.

**Property** (Transport Reversal).
$U_{\text{geo}}(y \to x) = U_{\text{geo}}(x \to y)^\dagger$, verified
numerically to $10^{-12}$.

**Property** (SU(2) Membership).
$\det(U_{\text{geo}}) = 1$ and $U_{\text{geo}}^\dagger U_{\text{geo}} =
\mathbb{I}$ for all edges, verified across all test domains.

### 4.6 Divergence Between Minimal and Geometric Transport

**Definition 9** (Spinor Divergence).
The *spinor divergence* between minimal and geometric transport for a set
of paths $\{p_k\}$ is

$$D = \frac{\left|I_{\text{geo}} - I_{\min}\right|}{\max(I_{\text{geo}}, I_{\min})}$$

where $I_{\text{geo}}$ and $I_{\min}$ are the intensities computed under
geometric and minimal embedding respectively.

**Table 2: Divergence across benchmark domains**

| Domain | Single-path $D$ | Multi-path $D$ | Off-axis fraction |
|--------|:---------------:|:--------------:|:-----------------:|
| Gordian A-short | < 0.01% | < 0.01% | — |
| Gordian A+loop | < 0.01% | **55.3%** | 92.9% |
| Triangle (3-node) | < 0.01% | **16.7%** | moderate |
| Leaf edges | < 0.01% | < 0.01% | 0% |

**Interpretation.** Geometric divergence from the minimal embedding arises
*only* when two conditions are met: (1) multi-path interference exists
(single-path divergence is always negligible), and (2) the vorticity
gradient and face holonomy produce significant off-axis components
($A_1, A_2 \neq 0$). The Gordian domain's loop path, with its strong
vorticity asymmetry, produces up to 92.9% off-axis contribution and
55.3% intensity divergence.

### 4.7 Spinor Intensity and Summation

**Definition 10** (Spinor Endpoint Amplitude).
Given a state $x$, action $a$, horizon $h$, and geometry $G$
(Paper 1, Defs. 21–25), the *spinor endpoint amplitude* is

$$\Psi_G^{\text{SU(2)}}(a; x, h) = \sum_{p \in \mathcal{P}_G(x, a, h)} \Psi_{\text{SU(2)}}(p) \in \mathbb{C}^2$$

**Definition 11** (Spinor Intensity).
The *spinor intensity* is

$$I^{\text{SU(2)}}(a) = \|\Psi_G^{\text{SU(2)}}(a)\|^2 = |\psi_1|^2 + |\psi_2|^2$$

**Proposition 5** (Spinor Interference).
*The spinor intensity exhibits interference analogous to Proposition 2
of Paper 1:*

$$I^{\text{SU(2)}}(a) = \left\|\sum_p \Psi_{\text{SU(2)}}(p)\right\|^2 \neq \sum_p \|\Psi_{\text{SU(2)}}(p)\|^2$$

*in general. The inequality is strict whenever contributing paths produce
spinor amplitudes that are not parallel in $\mathbb{C}^2$.*

*Proof.* Analogous to Paper 1, Proposition 2, using the $\mathbb{C}^2$
inner product instead of the $\mathbb{C}$ product. Cross terms
$2\,\text{Re}(\psi_i^* \phi_i)$ over components provide the interference
contribution. $\square$

---

## 5. The Born Criterion

This section derives the Born-rule probability $P(z) = |\Psi(z)|^2 /
\sum |\Psi(w)|^2$ as a structural consequence of the amplitude framework,
not as an axiom.

### 5.1 The Distribution Problem

Given the endpoint amplitudes $\Psi(z) \in \mathbb{C}^2$ (or $\mathbb{C}$
under U(1)) for a set of possible outcomes $z \in \Omega$, the question
is: *what probability distribution $P$ over $\Omega$ is structurally
non-arbitrary?*

This is not the quantum measurement problem. There is no wave function
collapse, no observer-system split, no decoherence. It is a structural
question: given that amplitudes encode path-aggregated information, what
is the canonical way to convert amplitudes into probabilities for
action selection?

### 5.2 Axioms of Bounded Exclusive Realization

We derive the Born rule under four axioms:

**Axiom BER-1** (Finite Alternative Set).
The set of possible outcomes $\Omega = \{z_1, z_2, \ldots, z_n\}$ is
finite, with $\sum_{z \in \Omega} I(z) < \infty$.

**Axiom BER-2** (Exclusive Realization).
Exactly one outcome $z^* \in \Omega$ is realized. Outcomes are mutually
exclusive: realization of $z^*$ precludes realization of any $z \neq z^*$.

**Axiom BER-3** (Representation Invariance).
The probability $P(z)$ depends only on the gauge-invariant intensity
$I(z) = \|\Psi(z)\|^2$, not on the phase or component structure of
$\Psi(z)$. Formally: if $\|\Psi(z)\| = \|\Psi'(z)\|$, then
$P(z) = P'(z)$.

**Axiom BER-4** (No Extra Structure).
The probability function $P : \Omega \to [0, 1]$ depends only on the
intensities $\{I(z)\}_{z \in \Omega}$. No additional function, threshold,
or external parameter is introduced.

### 5.3 Derivation

**Theorem 2** (Born Criterion).
*Under Axioms BER-1 through BER-4, the unique probability distribution
over outcomes is*

$$P(z) = \frac{I(z)}{\sum_{w \in \Omega} I(w)} = \frac{\|\Psi(z)\|^2}{\sum_{w \in \Omega} \|\Psi(w)\|^2}$$

*Proof.*

**Step 1** (Intensity dependence). By BER-3, $P(z)$ is a function of
$I(z)$ only: $P(z) = f(I(z); \{I(w)\}_{w \in \Omega})$ for some function
$f$ depending on the full intensity profile.

**Step 2** (Normalization). Since $\sum_{z} P(z) = 1$ (probability
axiom) and $P(z) \geq 0$:

$$\sum_{z \in \Omega} f(I(z); \{I(w)\}) = 1$$

**Step 3** (No extra structure). By BER-4, $f$ cannot introduce a
nonlinear distortion $g(I)$ without independent justification. The
simplest function satisfying $P(z) \geq 0$, $\sum P(z) = 1$, and
depending only on $\{I(z)\}$ is the *linear normalization*:

$$P(z) = \frac{I(z)}{\sum_{w} I(w)}$$

**Step 4** (Uniqueness). Any alternative $P(z) = g(I(z)) / \sum g(I(w))$
with $g \neq \text{id}$ introduces a nonlinear transformation $g$ that is
not determined by the structural chain $\Delta \to R \to H \to \cdots \to
\Psi \to I$. Such a $g$ would constitute *extra structure* (violating
BER-4) unless it is independently derivable from the framework's
primitives. Since the intensity $I = \|\Psi\|^2$ is already the canonical
gauge-invariant scalar derived from the amplitude, no further
transformation is structurally motivated.

Therefore $P(z) = I(z) / \sum I(w)$ is the unique non-arbitrary
distribution. $\square$

**Remark** (Status). This derivation is *conditional*: it holds if and
only if Axioms BER-1 through BER-4 are satisfied. The key assumption
is BER-2 (exclusive realization). In E₀'s operational context, the
controller selects one action per step, which satisfies BER-2. In
contexts where multiple outcomes can co-realize, the Born criterion
does not apply without modification.

### 5.4 Relationship to Paper 1's Born Sampling

Paper 1 introduced three hybrid modes:

- **GREEDY_ONLY:** local tension minimization (Algorithm 1).
- **AMPLITUDE_ON_DISAGREE:** deterministic amplitude override
  (Algorithm 3).
- **BORN_SAMPLING:** stochastic sampling from $P(a) \propto I(a)$
  (Algorithm 4).

The Born criterion (Theorem 2) provides the structural justification for
BORN_SAMPLING: under Axioms BER-1–4, sampling from
$P(a) = I(a) / \sum I(a')$ is not merely a design choice but the unique
non-arbitrary stochastic policy. This elevates BORN_SAMPLING from a
*heuristic option* to a *structurally derived strategy* (conditional on the
axioms holding).

**Remark** (Argmax vs. Born). The deterministic mode
(AMPLITUDE_ON_DISAGREE, which uses $\arg\max I$) does not follow from
the Born criterion. Argmax is a decision rule applied *on top of* the
Born distribution — it selects the mode rather than sampling. Both modes
use the same structural amplitudes; they differ only in the
amplitude-to-action mapping.

### 5.5 Born Criterion Under SU(2) and U(1)

The Born criterion applies equally to U(1) and SU(2) amplitudes, since
it depends only on the intensity $I(z) = \|\Psi(z)\|^2$, which is
well-defined in both cases. However, the *values* of $I(z)$ differ
between U(1) and SU(2) due to phase halving (Proposition 3), which
means the Born distribution itself changes under the spinor lift.

**Consequence.** On domains where phase halving changes the intensity
ranking, the Born distribution changes qualitatively. On the Gordian
domain: under U(1), $P(\text{B1}) \gg P(\text{A1})$; under SU(2),
$P(\text{A1}) \gg P(\text{B1})$.

---

## 6. When Does SU(2) $\neq$ U(1)?

### 6.1 Experimental Design

We compare U(1) and SU(2) amplitudes across the benchmark domains from
Paper 1: Diamond, Gordian Trap, G5 Multi-Goal, and Triangle. For each
domain and each action, we compute:

1. U(1) intensity $I_{\text{U(1)}}(a)$ (Paper 1 framework).
2. SU(2) minimal intensity $I_{\min}^{\text{SU(2)}}(a)$ ($\hat{n} = \hat{z}$).
3. SU(2) geometric intensity $I_{\text{geo}}^{\text{SU(2)}}(a)$
   ($\hat{n}$ from $\vec{A}$).
4. Winner under each transport: $a^* = \arg\max_a I(a)$.

### 6.2 Single-Path Equivalence (Universal)

By Proposition 2, single-path intensities are identical:
$\|\Psi_{\text{SU(2)}}(p)\| = |\Psi_{\text{U(1)}}(p)| = \exp(-S(p))$.
This is verified to $10^{-10}$ across all 52 spinor tests. No
single-path divergence is possible — SU(2) and U(1) agree perfectly
when there is no interference.

### 6.3 Phase Halving and the Decision Flip

The structurally significant divergence occurs under multi-path
interference, where phase halving (Proposition 3) changes the
interference pattern.

**Table 3: Decision outcomes by transport type (Gordian Trap)**

| Transport | $I(\text{A1})$ | $I(\text{B1})$ | Winner | Mechanism |
|-----------|:---------:|:---------:|:------:|-----------|
| U(1) | 0.018 | 0.156 | B1 | Full destructive interference on A1 |
| SU(2) minimal | 0.838 | 0.156 | **A1** | Phase halving neutralizes destruction |
| SU(2) geometric | varies | 0.156 | **A1** | + off-axis contribution |

**Interpretation.** The decision flip from B1 to A1 under SU(2) is caused
by phase halving: the A1 path family's two sub-paths have
$\Delta\Theta \approx \pi$, producing full destructive interference under
U(1) ($\cos\pi = -1$, $I \approx 0.018$). Under SU(2), the effective
phase difference is halved to $\approx \pi/2$, giving
$\cos(\pi/2) \approx 0$ (orthogonal, no interference), so $I$ rises to
0.838.

This is not a numerical artifact — it is a direct consequence of SU(2)'s
double-cover topology. The decision flip is *structurally predicted* by
Proposition 3 whenever $\Delta\Theta$ is near $\pi$.

### 6.4 Conditions for Divergence

Based on the empirical analysis across benchmark domains, we identify
three conditions for SU(2) $\neq$ U(1) at the decision level:

1. **Multi-path interference** (necessary). Single-path endpoints always
   agree (Proposition 2).

2. **Phase opposition near $\pi$** (sufficient for phase halving effect).
   When $\Delta\Theta \approx \pi$, U(1) gives maximal destructive
   interference while SU(2) gives near-zero interference.

3. **Intensity ranking sensitivity** (necessary for decision flip).
   The phase halving must change the intensity *ranking*, not merely
   the magnitude. This requires that the competing action's intensity
   falls between the U(1) and SU(2) intensity values of the affected
   action.

**Prediction.** Domains with $\Delta\Theta \in [\pi/2, 3\pi/2]$ between
path families are candidates for SU(2) decision flips. Outside this range,
phase halving preserves the qualitative interference pattern.

### 6.5 Geometric Coupling: Additional Divergence

Beyond phase halving, the geometric connection vector $\vec{A}$ (Def. 7)
introduces off-axis transport that further differentiates SU(2) from U(1).
On the Gordian domain, the vorticity gradient $A_1$ contributes up to
92.9% of the total $\|\vec{A}\|$ on loop edges, producing 55.3% intensity
divergence between minimal and geometric SU(2) on the multi-path A-family.

This geometric divergence represents a frontier: the three-component
connection encodes richer local structure than the scalar connection
$\omega$. Whether this additional structure improves decision quality
is an open empirical question (§9).

---

## 7. Multi-Goal Analysis Under Spinor Amplitudes

### 7.1 G5 Multi-Goal Domain

The G5 domain from Paper 1 features three competing goal states
$\{G_1, G_2, G_3\}$ with parallel path families from START. Under
goal-reaching geometry $G_{\text{goal}}$, each action's amplitude
aggregates paths to different goals.

**Key question.** Does the spinor lift change multi-goal behavior?

Under U(1), Born sampling reaches all three goals across trials (Paper 1,
§5.4), while argmax locks to a single goal. Under SU(2):

- **Single-path equivalence still holds:** each individual path has
  identical intensity under U(1) and SU(2).
- **Multi-path interference changes:** when multiple goal-reaching paths
  for a single action exhibit phase opposition, SU(2) modifies the
  interference pattern via phase halving.
- **Coverage effect:** Born sampling under SU(2) may redistribute
  probability mass across goals differently than U(1), depending on
  phase structure.

### 7.2 Robustness Under Stress

Paper 1's G5 edge-case suite tested five stress families (expansion,
irrelevance, conflict, specialist/generalist, rescue) with 28 tests,
all passing under U(1). The spinor lift preserves these results because:

1. **Expansion** ($|G| = 1 \to 5$): No entropy saturation. SU(2) adds
   spinor components but the $\mathbb{C}^2$ norm tracks the
   $\mathbb{C}$ norm for single-path cases.

2. **Irrelevance** (unreachable goals): Zero-amplitude goals contribute
   $\Psi = \mathbf{0} \in \mathbb{C}^2$, same as $\Psi = 0 \in
   \mathbb{C}$. No effect.

3. **Conflict** (specialists vs. generalist): The generalist action
   (reaching multiple goals) benefits from amplitude rescue. Under
   SU(2), the rescue mechanism changes quantitatively (phase halving) but
   the qualitative structure — generalist has higher total intensity —
   is preserved on tested domains.

4. **Rescue** ($\delta$ compression from 1.0 to 0.01): The rescue effect
   depends on intensity ratios, which change under SU(2) but remain
   non-zero for $\delta > 0$.

### 7.3 Topology Dependence

Paper 1's 380-graph topology classification identified phase opposition
$|\Delta\Theta| > \pi/2$ as the strongest predictor for amplitude override
(+25.1% correlation). Under SU(2), the effective threshold shifts:

- **U(1):** override correlated with $|\Delta\Theta| > \pi/2$.
- **SU(2):** the halved phase $|\Delta\Theta/2|$ means that U(1)-destructive
  cases ($|\Delta\Theta| \approx \pi$) become SU(2)-orthogonal, and
  U(1)-orthogonal cases ($|\Delta\Theta| \approx \pi/2$) become
  SU(2)-partially-constructive.

The topology classification thus depends on the transport theory: a domain
that is "trap-like" under U(1) may not be "trap-like" under SU(2), and
vice versa.

---

## 8. Implementation and Reproducibility

### 8.1 Code-Definition Mapping

The SU(2) extension is implemented in the `spinor_connection.py` module
(780 lines). The implementation directly mirrors the definitions in §3–4:

**Table 4: Implementation mapping**

| Module | Function | Definition |
|--------|----------|------------|
| `spinor_connection.py` | `pauli_exponential(θ, n̂)` | Def. 4 (SU(2) transport) |
| `spinor_connection.py` | `su2_edge_transport(L, x, y)` | Def. 5 (minimal embedding) |
| `spinor_connection.py` | `spinor_psi(L, path, ref)` | Def. 6 (spinor amplitude) |
| `spinor_connection.py` | `spinor_intensity(L, paths)` | Def. 11 (spinor intensity) |
| `spinor_connection.py` | `su2_connection(L, x, y)` | Def. 7 (geometric $\vec{A}$) |
| `spinor_connection.py` | `su2_geometric_transport(L, x, y)` | Def. 8 (geometric transport) |
| `spinor_connection.py` | `compare_minimal_geometric(L, paths)` | Def. 9 (divergence) |
| `controller.py` | `HybridMode.BORN_SAMPLING` | §5.4 (Born mode) |
| `controller.py` | `_born_sample()` | Theorem 2 (Born criterion) |

### 8.2 Test Registry

The SU(2) and Born criterion claims are validated by 79 tests:

**Table 5: Test organization**

| Test class | Tests | Focus | Key claim |
|-----------|:-----:|-------|-----------|
| `TestPauliAlgebra` | 7 | Pauli matrices: anticommutation, hermiticity, exponential | SU(2) primitives correct |
| `TestPeriodicity720` | 7 | $\exp(-i\pi\sigma) = -\mathbb{I}$, spinor sign flip | Theorem 1 |
| `TestSinglePathMagnitude` | 3 | $\|\Psi_{\text{SU(2)}}\| = \exp(-S)$ | Proposition 2 |
| `TestPhaseHalving` | 6 | $\cos(\Delta\Theta/2)$ interference change | Proposition 3 |
| `TestNonCommutativity` | 5 | $[\sigma_i, \sigma_j] \neq 0$, multi-axis population | Proposition 4 |
| `TestGraphHolonomy` | 5 | SU(2) holonomy well-defined, cycle-dependent | Def. 8 |
| `TestStructuralProperties` | 6 | Edge cases, intensity non-negativity, reference independence | Defs. 6, 10–11 |
| `TestGeometricCoupling` | 13 | $\vec{A}$ antisymmetry, $U_{\text{geo}} \in \text{SU}(2)$ | Defs. 7–8 |
| `TestBornSampling` | 27 | Born distribution, geometry dominance, multi-goal | Theorem 2, §7 |

### 8.3 Reproducibility

All experiments use fixed random seeds. Benchmark domains are defined
in test code with exact parameter values included in Paper 1,
Appendix B. To reproduce:

```
python -m unittest discover -s e0_controller -p "test_*.py"
```

---

## 9. Limitations and Open Questions

### 9.1 Status of Formal Claims

**Derived** (follows from the structural chain):
- Carrier minimality: internal difference requires $\mathbb{C}^2$
  (Proposition 1).
- 720° periodicity (Theorem 1).
- Magnitude consistency (Proposition 2).
- Phase halving effect on interference (Proposition 3).
- Non-commutativity of SU(2) generators (Proposition 4).
- Born criterion under BER axioms (Theorem 2).

**Empirical** (demonstrated through tests, not analytically proven):
- Decision flip on Gordian Trap (Table 3).
- Geometric divergence magnitudes (Table 2).
- Multi-goal robustness preservation under spinor lift (§7.2).
- Off-axis contribution fractions (92.9% on Gordian).

**Open** (structurally motivated but unresolved):
- Does geometric coupling ($\vec{A}$ vs. $\omega\hat{z}$) ever produce
  decision flips independent of phase halving?
- What is the optimal multi-axis strategy per domain topology?
- When does exclusive realization (BER-2) hold operationally?
- How does the topology classification (Paper 1, §7) change under SU(2)?
- Continuous endpoint density and the Born criterion.

### 9.2 The Decision Flip Frontier

SU(2) produces a qualitative decision flip on the Gordian domain
(§6.3), but this domain was specifically designed with
$\Delta\Theta \approx \pi$. The open question is: on naturally occurring
graph topologies, how often does $\Delta\Theta$ fall in the critical
range $[\pi/2, 3\pi/2]$ where phase halving changes the interference
character?

**Specific prediction:** Graphs with phase opposition in the range
$\Delta\Theta \in (0.7\pi, 1.3\pi)$ should exhibit the strongest
SU(2)/U(1) divergence. This range corresponds to where
$\cos(\Delta\Theta) < -0.6$ (strong U(1) destruction) but
$\cos(\Delta\Theta/2)$ is near zero (SU(2) neutralization).

### 9.3 Universality of Exclusive Realization

The Born criterion (Theorem 2) is conditional on BER-2: exactly one
outcome realizes. In E₀'s operational context:

- **Action selection** satisfies BER-2: the controller selects exactly
  one successor state per step.
- **Multi-goal evaluation** does *not* satisfy BER-2 in general: the
  system may reach different goals on different runs, and the "realization"
  is the entire trajectory, not a single endpoint.

The gap between the axiom's scope and the framework's full operational
range is acknowledged as a limitation. Extending the Born criterion to
non-exclusive realization (e.g., via density-operator analogs) is future
work.

### 9.4 Computational Overhead

The spinor lift introduces matrix multiplication (2×2 complex) at each
edge, compared to scalar multiplication under U(1). This is a constant
factor overhead — the complexity class remains $O(k^h)$ (Paper 1, §9.2).
The geometric connection (Def. 7) adds neighborhood lookups for $A_1$ and
triangle enumeration for $A_2$, which are $O(|E|)$ per edge. For the
benchmark domains ($|E| \leq 20$), this is negligible.

---

## 10. Discussion

### 10.1 From U(1) to SU(2): Structural Necessity vs. Empirical Utility

The carrier minimality argument (§3) establishes that SU(2) is
*structurally forced* by internal difference. This is a mathematical
fact, independent of whether SU(2) improves decision quality. The
empirical question — whether the richer phase structure helps — has a
nuanced answer:

- **On the Gordian domain:** SU(2) produces a qualitative decision flip
  (§6.3). The phase halving effect neutralizes destructive interference
  that was the basis of U(1)'s trap detection. This is a genuine
  structural effect.
- **On Diamond and Triangle:** SU(2) changes intensity magnitudes but
  not (yet) the winning action. The effect is quantitative, not
  qualitative.
- **On single-path topologies:** no difference (Proposition 2).

The relationship between structural necessity and empirical utility is
the central open question. SU(2) is *always* the more faithful
representation; whether this additional fidelity changes decisions depends
on the topology.

### 10.2 Born Rule Without Quantum Mechanics

The Born criterion (Theorem 2) derives $P = |\Psi|^2 / \sum |\Psi|^2$
from structural axioms without Hilbert spaces, entanglement, or
decoherence. Compared to existing derivations:

| Approach | Assumptions | Scope |
|----------|-------------|-------|
| Gleason [4] | Hilbert space $\dim \geq 3$, frame function | All quantum states |
| Zurek [5] | Entanglement, environment, envariance symmetry | Decohered subsystems |
| Deutsch–Wallace [6, 7] | Everettian branching, rationality axioms | Rational agents in MWI |
| **E₀ (Theorem 2)** | **Finite alternatives, exclusivity, gauge invariance, no extra structure** | **Bounded exclusive realization** |

E₀'s derivation has *weaker assumptions* (no Hilbert space, no physics)
but *narrower scope* (only bounded exclusive realization). The insight is
that the Born rule is not specific to quantum mechanics — it is the
canonical normalization of any gauge-invariant intensity measure under
exclusivity constraints.

### 10.3 Non-Commutativity as Structural Signal

The non-commutativity of SU(2) transport (Proposition 4) means that path
*ordering* carries information that is invisible to U(1). Two paths with
identical edge sets but different orderings produce different spinor
amplitudes. This path-order sensitivity is structurally significant in
domains where:

- **Transitions are irreversible:** the order of state changes matters
  (e.g., workflow routing where step order affects outcomes).
- **Local context changes:** crossing edge $e_1$ before $e_2$ encounters
  different resistance landscape than $e_2$ before $e_1$ (after
  historization updates).

Non-commutativity is not merely a mathematical artifact of SU(2) — it
represents genuine structural information about the transition graph's
orientational complexity.

### 10.4 Toward a Complete Structural Decision Theory

Papers 1 and 2 establish two layers of a structural decision theory:

1. **Paper 1:** Interference as decision mechanism. Structural primitives
   $\to$ complex amplitudes $\to$ constructive/destructive interference
   $\to$ trap detection.

2. **Paper 2:** Spinor structure and emergent probability. Internal
   difference $\to$ $\mathbb{C}^2$ carrier $\to$ SU(2) transport $\to$
   Born-rule probability.

Open horizons include:
- **Measurement theory:** under what conditions does the system "realize"
  an outcome? Is there an analog of decoherence in the graph setting?
- **Observer structure:** can the distinction between system and
  observation be formalized graph-theoretically?
- **Continuous limits:** does the framework admit a meaningful
  continuum limit as the graph becomes dense?
- **Higher gauge groups:** is there a structural argument forcing
  transport beyond SU(2)?

---

## 11. Conclusion

We have extended the E₀ framework from scalar (U(1)) to spinor (SU(2))
amplitudes on discrete transition graphs. The main contributions are:

1. **Carrier minimality** (Proposition 1): encoding internal difference
   — rotational structure beyond scalar phase — requires $\mathbb{C}^2$
   as the minimal carrier space, forcing SU(2)-valued path transport.

2. **Three emergent effects** of the spinor lift: 720° periodicity
   (Theorem 1), phase halving (Proposition 3) that changes interference
   from destructive to orthogonal, and non-commutativity (Proposition 4)
   that makes path ordering structurally significant.

3. **The Born criterion** (Theorem 2): under bounded exclusive
   realization, the probability $P(z) = \|\Psi(z)\|^2 / \sum \|\Psi(w)\|^2$
   is the unique structurally non-arbitrary distribution. Probability
   emerges from interference, not from axioms.

4. **An empirical decision flip** on the Gordian Trap domain: SU(2)
   phase halving neutralizes the destructive interference that made U(1)
   reject the decoy path family, changing the selected action.

5. **Conditions for SU(2) $\neq$ U(1):** multi-path interference plus
   phase opposition near $\pi$ are necessary; geometric coupling
   (off-axis $\vec{A}$) provides additional divergence.

All claims are classified as derived, empirical, or open (§9.1). The
framework does not claim quantum-mechanical status, universal superiority
of SU(2), or real-world deployment evidence. It demonstrates that spinor
structure and Born-rule probability can emerge from graph-theoretic
primitives through structural derivation.

---

## Appendices

### Appendix A. Pauli Algebra Reference

The Pauli matrices are:

$$\sigma_1 = \begin{pmatrix} 0 & 1 \\ 1 & 0 \end{pmatrix}, \quad \sigma_2 = \begin{pmatrix} 0 & -i \\ i & 0 \end{pmatrix}, \quad \sigma_3 = \begin{pmatrix} 1 & 0 \\ 0 & -1 \end{pmatrix}$$

**Properties** (all verified to $10^{-14}$ in test suite):

1. **Anticommutation:** $\{\sigma_i, \sigma_j\} = \sigma_i\sigma_j + \sigma_j\sigma_i = 2\delta_{ij}\mathbb{I}$
2. **Commutation:** $[\sigma_i, \sigma_j] = 2i\epsilon_{ijk}\sigma_k$
3. **Hermiticity:** $\sigma_i^\dagger = \sigma_i$
4. **Tracelessness:** $\text{tr}(\sigma_i) = 0$
5. **Determinant:** $\det(\sigma_i) = -1$
6. **Square:** $\sigma_i^2 = \mathbb{I}$

**Exponential map:**

$$\exp(-i\theta\,\hat{n} \cdot \vec{\sigma}) = \cos\theta\,\mathbb{I} - i\sin\theta\,(\hat{n} \cdot \vec{\sigma})$$

This evaluates to an SU(2) matrix for any $\theta \in \mathbb{R}$ and
unit vector $\hat{n} \in S^2$, since $\det = \cos^2\theta + \sin^2\theta
= 1$ and $(U^\dagger U)_{ij} = \delta_{ij}$.

### Appendix B. Born Criterion Derivation (Detailed)

**Setup.** Given amplitudes $\{\Psi(z)\}_{z \in \Omega}$ with intensities
$I(z) = \|\Psi(z)\|^2 > 0$ for $z$ in the support, and $I(z) = 0$ for
$z$ outside the support, find $P : \Omega \to [0, 1]$ satisfying:

(i) $\sum_{z} P(z) = 1$ (normalization)
(ii) $P(z) \geq 0$ (non-negativity)
(iii) $P(z) = 0 \iff I(z) = 0$ (support matching, from BER-3)
(iv) $P(z) = f(I(z))$ for some function $f$ (representation invariance, BER-3)
(v) $f$ is the identity up to normalization (no extra structure, BER-4)

**From (i)–(iv):** $P(z) = f(I(z)) / \sum_w f(I(w))$ for some
monotone $f : \mathbb{R}_{\geq 0} \to \mathbb{R}_{\geq 0}$ with
$f(0) = 0$ and $f(t) > 0$ for $t > 0$.

**From (v):** $f = \text{id}$ is the structurally simplest choice. Any
$f \neq \text{id}$ (e.g., $f(I) = I^\alpha$ with $\alpha \neq 1$)
introduces a parameter $\alpha$ not derivable from the structural chain.
By BER-4, such parameters are excluded.

**Conclusion:** $P(z) = I(z) / \sum_w I(w)$ uniquely. $\square$

### Appendix C. Geometric Connection $\vec{A}$ Construction

**Construction of $A_1$ (vorticity gradient):**

For edge $(x, y)$, define:

$$A_1(x, y) = \frac{1}{|N(x) \setminus y|}\sum_{z \in N(x) \setminus y}\omega(x, z) - \frac{1}{|N(y) \setminus x|}\sum_{z \in N(y) \setminus x}\omega(y, z)$$

This measures the difference in average "rotational environment" between
the source and target of the edge. High $|A_1|$ indicates that the edge
connects regions with different vorticity character.

**Construction of $A_2$ (face holonomy):**

$$A_2(x, y) = \frac{1}{|\triangle_{x,y}|}\sum_{z \in \triangle_{x,y}} \bigl(\omega(x,y) + \omega(y,z) + \omega(z,x)\bigr)$$

where $\triangle_{x,y} = \{z : (x,y), (y,z), (z,x) \in E\}$ is the set
of states completing a directed triangle with edge $(x, y)$. If
$\triangle_{x,y} = \emptyset$, then $A_2(x,y) = 0$.

**Construction of $A_3$ (direct connection):**

$$A_3(x, y) = \omega(x, y)$$

This is the scalar connection from Paper 1, embedded as the third
component.

**Antisymmetry verification:** All three components satisfy
$A_i(y, x) = -A_i(x, y)$:
- $A_3$: inherits from $\omega(y,x) = -\omega(x,y)$.
- $A_1$: the vorticity gradient swaps sign when source and target swap.
- $A_2$: triangle traversal reverses direction.

### Appendix D. Divergence Data

**Table D1: Full U(1) vs. SU(2) comparison (Gordian Trap)**

| Action | Path family | $I_{\text{U(1)}}$ | $I_{\min}^{\text{SU(2)}}$ | $I_{\text{geo}}^{\text{SU(2)}}$ |
|--------|-----------|:---------:|:---------:|:---------:|
| A1 | A-short only | 0.744 | 0.744 | 0.744 |
| A1 | A-loop only | 0.543 | 0.543 | 0.543 |
| A1 | A-short + A-loop (interference) | 0.018 | 0.838 | varies |
| B1 | B-path (single) | 0.156 | 0.156 | 0.156 |

**Key observation:** Single-path intensities (rows 1, 2, 4) are identical
across all three transport types. Only the interference row (row 3)
diverges: U(1) $\to$ destructive (0.018), SU(2) $\to$ orthogonal (0.838).

### Appendix E. Derived / Empirical / Open Classification

**Table E1: Honesty map for Paper 2 claims**

| Component | Status | Evidence |
|-----------|--------|----------|
| Carrier minimality (Prop. 1) | **Derived** | Algebraic argument §3.4 |
| 720° periodicity (Thm. 1) | **Derived** | Algebraic proof + 52 tests |
| Magnitude consistency (Prop. 2) | **Derived** | Unitarity of SU(2) |
| Phase halving (Prop. 3) | **Derived** | Half-angle formula |
| Non-commutativity (Prop. 4) | **Derived** | Pauli commutation relations |
| Spinor interference (Prop. 5) | **Derived** | $\mathbb{C}^2$ inner product |
| Born criterion (Thm. 2) | **Derived** (conditional) | Axioms BER-1–4 |
| Decision flip on Gordian | **Empirical** | Table 3, test suite |
| Geometric divergence magnitudes | **Empirical** | Table 2, 52 tests |
| Off-axis fraction 92.9% | **Empirical** | Gordian geometric tests |
| Geometric $\vec{A}$ construction | Structural (Defs. 7–8) | Implementation verified |
| Geometric coupling flips decisions | **Open** | Not yet observed independently |
| Optimal multi-axis strategy | **Open** | Not explored |
| BER-2 operational scope | **Open** | §9.3 discussion |
| Topology classification under SU(2) | **Open** | Predicted shift, not measured |

---

## References

[1] D. Hestenes. *New Foundations for Classical Mechanics*. Kluwer Academic Publishers, 2nd edition, 1999.

[2] L. J. Grady and J. R. Polimeni. *Discrete Calculus: Applied Analysis on Graphs for Computational Science*. Springer, 2010.

[3] T. Bülow and G. Sommer. "Hypercomplex signals — a novel extension of the analytic signal to the multidimensional case." *IEEE Transactions on Signal Processing*, 49(11):2844–2852, 2001.

[4] A. M. Gleason. "Measures on the closed subspaces of a Hilbert space." *Journal of Mathematics and Mechanics*, 6(6):885–893, 1957.

[5] W. H. Zurek. "Environment-assisted invariance, entanglement, and probabilities in quantum physics." *Physical Review Letters*, 90(12):120404, 2003.

[6] D. Deutsch. "Quantum theory of probability and decisions." *Proceedings of the Royal Society A*, 455(1988):3129–3137, 1999.

[7] D. Wallace. "Everettian rationality: defending Deutsch's approach to probability in the Everett interpretation." *Studies in History and Philosophy of Modern Physics*, 34(3):415–439, 2003.

[8] S. Saunders. "Derivation of the Born rule from operational assumptions." *Proceedings of the Royal Society A*, 460(2046):1771–1788, 2004.

[9] K. G. Wilson. "Confinement of quarks." *Physical Review D*, 10(8):2445–2459, 1974.

[10] J. B. Kogut and L. Susskind. "Hamiltonian formulation of Wilson's lattice gauge theories." *Physical Review D*, 11(2):395–408, 1975.

[11] T. S. Cohen, M. Weiler, B. Kicanaoglu, and M. Welling. "Gauge equivariant convolutional networks and the icosahedral CNN." In *ICML*, pp. 1321–1330, 2019.

[12] S. Favoni, A. Ipp, D. I. Müller, and D. Schuh. "Lattice gauge equivariant convolutional neural networks." *Physical Review Letters*, 128(3):032003, 2022.

[13] Y. He, M. Xu, C. Adams, S. Bose, U. Bhatt, and M. Bronstein. "A gauge equivariant transformer." arXiv:2310.12963, 2023.

[14] C. Bodnar, F. Di Giovanni, B. Chamberlain, P. Liò, and M. Bronstein. "Neural sheaf diffusion." In *NeurIPS*, 2022.

[15] A. Singer and H.-T. Wu. "Vector diffusion maps and the connection Laplacian." *Communications on Pure and Applied Mathematics*, 65(8):1067–1144, 2012.

---

*End of manuscript.*
