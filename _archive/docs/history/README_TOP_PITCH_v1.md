# README Top Pitch (Final Version)

## Primary (recommended for top of README)

E₀ is a structural transition framework with an executable hybrid controller.  
It combines local burden minimization with amplitude-based evaluation of coherent future path families.  
When these two views disagree, the system can follow the path with stronger structural future support instead of the locally cheapest step.  
This repository contains the canonical core, the controller, the amplitude layer, and fully integrated hybrid demos.

---

## Alternative (simpler / more accessible)

E₀ is a system for making decisions based on structure, not just immediate cost.  
Instead of only asking “what is the cheapest next step?”, it also evaluates which step belongs to the strongest coherent family of possible futures.  
In hybrid mode, this allows the system to avoid greedy traps and follow structurally better paths.

---

## Alternative (technical audience)

E₀ implements a historized structural controller extended with a complex path-amplitude layer.  
Actions are evaluated both by local burden and by bounded path-family intensities derived from Ψ(p)=exp(-S(p))exp(iΘ(p)).  
A hybrid arbitration mode resolves disagreements between these regimes, enabling phase-sensitive correction of greedy selection.
