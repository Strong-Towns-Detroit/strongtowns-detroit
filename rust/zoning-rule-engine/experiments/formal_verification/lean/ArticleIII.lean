/- Kernel-checkable model of the shared §50-3-10 boundary fixture.
   Run with: lean lean/ArticleIII.lean -/

inductive Concept where
  | agency | hearingForum | publishedNotice | publicHearing | legalRequirement
  deriving DecidableEq

structure Relation where
  name : String
  domain : Concept
  range : Concept
  deriving DecidableEq

def responsibleFor : Relation := ⟨"responsible_for", .agency, .publishedNotice⟩

def wellTyped (r : Relation) (subject object : Concept) : Prop :=
  r.domain = subject ∧ r.range = object

theorem responsibleFor_valid :
    wellTyped responsibleFor .agency .publishedNotice := by
  decide

theorem responsibleFor_rejects_reversal :
    ¬ wellTyped responsibleFor .publicHearing .agency := by
  decide

def noticeComplies (elapsedDays : Nat) : Bool := elapsedDays ≥ 15

theorem day14_fails : noticeComplies 14 = false := by decide
theorem day15_passes : noticeComplies 15 = true := by decide
theorem day16_passes : noticeComplies 16 = true := by decide

theorem syntax_independence
    (compileO1 compileO2 : Unit → Relation)
    (h1 : compileO1 () = responsibleFor)
    (h2 : compileO2 () = responsibleFor) :
    compileO1 () = compileO2 () := by
  rw [h1, h2]

