window.DSL_REVIEW_DATA = {
  "syntaxes": {
    "ontologies": [
      {
        "id": "o1",
        "name": "SDML-inspired",
        "character": "Module-oriented, low punctuation"
      },
      {
        "id": "o2",
        "name": "Manchester-inspired",
        "character": "Explicit labeled frames"
      },
      {
        "id": "o3",
        "name": "RDF/SHACL-inspired",
        "character": "Compact graph and constraint vocabulary"
      }
    ],
    "rules": [
      {
        "id": "r1",
        "name": "Provision + Boolean",
        "character": "Source-oriented named provisions"
      },
      {
        "id": "r2",
        "name": "Labeled provision",
        "character": "Verbose professional-review frames"
      },
      {
        "id": "r3",
        "name": "Datalog derivation",
        "character": "Compact normalized execution rules"
      }
    ]
  },
  "examples": [
    {
      "id": "notice",
      "citation": "\u00a750-3-10",
      "title": "Published-hearing notice",
      "pressure": "Typed relations, applicability, provenance, and an inclusive duration",
      "crate": "matrix_harness",
      "sources": {
        "ontologies": {
          "o1": {
            "path": "sdml_style/ontology.sdmlish",
            "text": "module detroit_hearings is\n\n  concept Agency\n  concept HearingForum\n  concept PublishedNotice\n  concept PublicHearing\n  concept LegalRequirement\n\n  individual BSEED is Agency, HearingForum\n  individual Chapter50 is LegalRequirement\n\n  relation responsible_for is\n    from Agency\n    to PublishedNotice\n  end\n\n  relation notice_for is\n    from PublishedNotice\n    to PublicHearing\n  end\n\n  relation forum_for is\n    from HearingForum\n    to PublicHearing\n  end\n\n  relation required_by is\n    from PublishedNotice\n    to LegalRequirement\n  end\n\n  relation precedes is\n    from PublishedNotice\n    to PublicHearing\n  end\n\nend\n"
          },
          "o2": {
            "path": "manchester_style/ontology.manchester",
            "text": "Ontology: DetroitHearings\n\nClass: Agency\nClass: HearingForum\nClass: PublishedNotice\nClass: PublicHearing\nClass: LegalRegime\n\nObjectProperty: responsibleFor\n  Domain: Agency\n  Range: PublishedNotice\n\nObjectProperty: forumFor\n  Domain: HearingForum\n  Range: PublicHearing\n\nObjectProperty: noticeFor\n  Domain: PublishedNotice\n  Range: PublicHearing\n\nObjectProperty: requiresPublishedNotice\n  Domain: LegalRegime\n  Range: PublishedNotice\n\nObjectProperty: precedes\n  Domain: PublishedNotice\n  Range: PublicHearing\n\nIndividual: BSEED\n  Types: Agency, HearingForum\n\nIndividual: Chapter50\n  Types: LegalRegime\n"
          },
          "o3": {
            "path": "rdf_datalog_style/ontology.zonto",
            "text": "# RDF/SHACL-inspired schema. This is intentionally a small experimental syntax.\nprefix detroit https://detroitmi.gov/zoning/\n\nclass Agency\nclass HearingForum\nclass PublishedNotice\nclass PublicHearing\nclass LegalRequirement\n\nproperty responsible_for domain Agency range PublishedNotice min 1\nproperty forum_for domain HearingForum range PublicHearing min 1\nproperty notice_for domain PublishedNotice range PublicHearing min 1\nproperty required_by domain PublishedNotice range LegalRequirement min 1\nproperty precedes domain PublishedNotice range PublicHearing min 1\n\nindividual BSEED types Agency,HearingForum\nindividual Chapter50 types LegalRequirement\n"
          }
        },
        "rules": {
          "r1": {
            "path": "sdml_style/article_iii.rules",
            "text": "module detroit_article_iii\nimport detroit_hearings\n\nprovision minimum_bseed_notice\n  id \"detroit:article-iii:block:79:proposition:1\"\n  source \"\u00a750-3-10\" quote \"Where the provisions of this chapter require that notice be published, the agency responsible for giving notice shall ensure that it is published in a newspaper of general circulation within the City. The notice shall be published:\"\n  source \"\u00a750-3-10(1)\" quote \"At least 15 days prior to a public hearing being held before the Buildings, Safety Engineering, and Environmental Department; or\"\n  given notice: PublishedNotice\n  given hearing: PublicHearing\n  given agency: Agency\n  applies when all\n    notice.required_by == Chapter50\n    notice.responsible_agency == agency\n    notice.hearing == hearing\n    hearing.forum == BSEED\n  require\n    notice.published_at <= hearing.starts_at - 15 days\nend\n"
          },
          "r2": {
            "path": "manchester_style/article_iii.rule",
            "text": "RuleModule: DetroitArticleIII\nImportOntology: DetroitHearings\n\nProvision: MinimumBseedNotice\n  PropositionId: detroit:article-iii:block:79:proposition:1\n  Citation: \u00a750-3-10(1)\n  SourceSpan: applicability | Where the provisions of this chapter require that notice be published, the agency responsible for giving notice shall ensure that it is published in a newspaper of general circulation within the City. The notice shall be published:\n  SourceSpan: deadline | At least 15 days prior to a public hearing being held before the Buildings, Safety Engineering, and Environmental Department; or\n  Given:\n    notice: PublishedNotice\n    hearing: PublicHearing\n    agency: Agency\n  AppliesWhenAll:\n    notice.requiredBy: Chapter50\n    notice.responsibleAgency: agency\n    notice.hearing: hearing\n    hearing.forum: BSEED\n  Duty:\n    bearer: agency\n    action: publish notice\n    deadline: no later than 15 days before hearing.startsAt\n"
          },
          "r3": {
            "path": "rdf_datalog_style/article_iii.rules",
            "text": "# The legal rule is a separate module importing the ontology vocabulary.\nmodule detroit.article_iii\nimport ontology.zonto\nid detroit:article-iii:block:79:proposition:1\nsource-span \u00a750-3-10 | Where the provisions of this chapter require that notice be published, the agency responsible for giving notice shall ensure that it is published in a newspaper of general circulation within the City. The notice shall be published:\nsource-span \u00a750-3-10(1) | At least 15 days prior to a public hearing being held before the Buildings, Safety Engineering, and Environmental Department; or\nobligation actor Agency action publish_notice\n\npublication_obligation_satisfied(\n  agency: Agency,\n  notice: Notice,\n  hearing: Hearing\n) :-\n  Notice is PublishedNotice,\n  Hearing is PublicHearing,\n  Agency is Agency,\n  Notice.required_by = Chapter50,\n  Notice.responsible_agency = Agency,\n  Notice.hearing = Hearing,\n  Hearing.forum = BSEED,\n  elapsed_days(\n    from: Notice.published_at,\n    until: Hearing.starts_at,\n    result: Days\n  ),\n  Days >= 15.\n"
          }
        }
      },
      "test_result": {
        "passed": false,
        "tests": [
          "o1_r1",
          "o1_r2",
          "o1_r3",
          "o2_r1",
          "o2_r2",
          "o2_r3",
          "o3_r1",
          "o3_r2",
          "o3_r3",
          "ontology_normal_forms_are_identical",
          "rule_normal_forms_are_identical"
        ],
        "count": 11,
        "failure": "error: test failed, to rerun pass `--lib`\n"
      }
    },
    {
      "id": "votes",
      "citation": "\u00a750-2-78",
      "title": "BZA voting threshold",
      "pressure": "Specialization, specific override, exact fraction, and rounding",
      "crate": "voting_threshold",
      "sources": {
        "ontologies": {
          "o1": {
            "path": "voting_threshold/ontology.sdmlish",
            "text": "module detroit_bza_voting is\n\n  concept DecisionMakingBody\n  concept BoardDecision\n  concept MatterKind\n\n  individual DetroitBZA is DecisionMakingBody\n  individual ReverseOrAdjustAdministrativeAction is MatterKind\n  individual ApplicantFavorableMatter is MatterKind\n  individual Variance is MatterKind\n  individual HardshipReliefUseVariance is MatterKind\n\n  relation decision_by is\n    from BoardDecision\n    to DecisionMakingBody\n  end\n\n  relation matter_kind is\n    from BoardDecision\n    to MatterKind\n  end\n\n  relation specializes is\n    from MatterKind\n    to MatterKind\n  end\n\n  measure authorized_members is\n    for DecisionMakingBody\n    value WholeCount\n  end\n\n  measure concurring_votes is\n    for BoardDecision\n    value WholeCount\n  end\n\n  fact specializes(HardshipReliefUseVariance, Variance)\n\nend\n"
          },
          "o2": {
            "path": "voting_threshold/ontology.manchester",
            "text": "Ontology: DetroitBzaVoting\n\nClass: DecisionMakingBody\nClass: BoardDecision\nClass: MatterKind\n\nIndividual: DetroitBZA\n  Types: DecisionMakingBody\nIndividual: ReverseOrAdjustAdministrativeAction\n  Types: MatterKind\nIndividual: ApplicantFavorableMatter\n  Types: MatterKind\nIndividual: Variance\n  Types: MatterKind\nIndividual: HardshipReliefUseVariance\n  Types: MatterKind\n  Facts: specializes Variance\n\nObjectProperty: decidedBy\n  Domain: BoardDecision\n  Range: DecisionMakingBody\nObjectProperty: hasMatterKind\n  Domain: BoardDecision\n  Range: MatterKind\nObjectProperty: specializes\n  Domain: MatterKind\n  Range: MatterKind\n\nDataProperty: authorizedMemberCount\n  Domain: DecisionMakingBody\n  Range: nonNegativeInteger\nDataProperty: concurringVoteCount\n  Domain: BoardDecision\n  Range: nonNegativeInteger\n"
          },
          "o3": {
            "path": "voting_threshold/ontology.zonto",
            "text": "prefix detroit https://detroitmi.gov/zoning/\n\nclass DecisionMakingBody\nclass BoardDecision\nclass MatterKind\n\nindividual DetroitBZA types DecisionMakingBody\nindividual ReverseOrAdjustAdministrativeAction types MatterKind\nindividual ApplicantFavorableMatter types MatterKind\nindividual Variance types MatterKind\nindividual HardshipReliefUseVariance types MatterKind\n\nproperty decision_by domain BoardDecision range DecisionMakingBody min 1 max 1\nproperty matter_kind domain BoardDecision range MatterKind min 1\nproperty specializes domain MatterKind range MatterKind\ndatatype authorized_members domain DecisionMakingBody range nonNegativeInteger min 1 max 1\ndatatype concurring_votes domain BoardDecision range nonNegativeInteger min 1 max 1\n\nfact specializes HardshipReliefUseVariance Variance\n"
          }
        },
        "rules": {
          "r1": {
            "path": "voting_threshold/rule.provision",
            "text": "module detroit_bza_voting_threshold\nimport detroit_bza_voting\n\nprovision concurring_vote_required\n  id \"detroit:article-ii:section-50-2-78:ordinary-threshold\"\n  source \"\u00a750-2-78\" quote \"The concurring vote of a majority of the members of the Board of Zoning Appeals shall be necessary to reverse or adjust any order, requirement, decision, or determination of any administrative official, or to decide in favor of the applicant on any matter upon which the Board is required to pass under this chapter, or to grant a variance in this chapter;\"\n  strength strict\n  given decision: BoardDecision\n  given board: DecisionMakingBody\n  if decision_by(decision, board) && board == DetroitBZA && matter_kind(decision, ReverseOrAdjustAdministrativeAction || ApplicantFavorableMatter || Variance) && !matter_kind(decision, HardshipReliefUseVariance)\n  require concurring_votes(decision) >= floor(authorized_members(board) / 2) + 1\nend\n\nprovision hardship_relief_override\n  id \"detroit:article-ii:section-50-2-78:hardship-override\"\n  source \"\u00a750-2-78 exception\" quote \"except that pursuant to Section 604(10) of the Michigan Zoning Enabling Act, being MCL 125.3604(10), the concurring vote of a two-thirds majority of the members of the Board shall be necessary to approve a variance from a use of land through a hardship relief petition as set forth in Article IV, Division 7, of this chapter.\"\n  strength strict\n  overrides concurring_vote_required\n  given decision: BoardDecision\n  given board: DecisionMakingBody\n  if decision_by(decision, board) && board == DetroitBZA && matter_kind(decision, HardshipReliefUseVariance)\n  require concurring_votes(decision) >= ceil(authorized_members(board) * 2 / 3)\nend\n"
          },
          "r2": {
            "path": "voting_threshold/rule.labeled",
            "text": "RuleModule: DetroitBzaVotingThreshold\nImportOntology: DetroitBzaVoting\n\nProvision: ConcurringVoteRequired\n  PropositionId: detroit:article-ii:section-50-2-78:ordinary-threshold\n  Citation: \u00a750-2-78\n  SourceSpan: ordinary | The concurring vote of a majority of the members of the Board of Zoning Appeals shall be necessary to reverse or adjust any order, requirement, decision, or determination of any administrative official, or to decide in favor of the applicant on any matter upon which the Board is required to pass under this chapter, or to grant a variance in this chapter;\n  Status: Strict\n  Given: decision BoardDecision\n  Given: board DecisionMakingBody\n  AppliesWhen: (decidedBy(decision, board) && board == DetroitBZA && hasMatterKind(decision, ReverseOrAdjustAdministrativeAction || ApplicantFavorableMatter || Variance) && !hasMatterKind(decision, HardshipReliefUseVariance))\n  RequiredVotes: floor(authorizedMemberCount(board) / 2) + 1\n\nProvision: HardshipReliefOverride\n  PropositionId: detroit:article-ii:section-50-2-78:hardship-override\n  Citation: \u00a750-2-78 exception; MCL 125.3604(10); Article IV, Division 7\n  SourceSpan: exception | except that pursuant to Section 604(10) of the Michigan Zoning Enabling Act, being MCL 125.3604(10), the concurring vote of a two-thirds majority of the members of the Board shall be necessary to approve a variance from a use of land through a hardship relief petition as set forth in Article IV, Division 7, of this chapter.\n  Status: Strict\n  Overrides: ConcurringVoteRequired\n  Given: decision BoardDecision\n  Given: board DecisionMakingBody\n  AppliesWhen: (decidedBy(decision, board) && board == DetroitBZA && hasMatterKind(decision, HardshipReliefUseVariance))\n  RequiredVotes: ceil(authorizedMemberCount(board) * 2 / 3)\n"
          },
          "r3": {
            "path": "voting_threshold/rule.datalog",
            "text": "module detroit.bza_voting_threshold\nimport ontology.zonto\n\nsource ordinary id detroit:article-ii:section-50-2-78:ordinary-threshold | The concurring vote of a majority of the members of the Board of Zoning Appeals shall be necessary to reverse or adjust any order, requirement, decision, or determination of any administrative official, or to decide in favor of the applicant on any matter upon which the Board is required to pass under this chapter, or to grant a variance in this chapter;\nsource override id detroit:article-ii:section-50-2-78:hardship-override | except that pursuant to Section 604(10) of the Michigan Zoning Enabling Act, being MCL 125.3604(10), the concurring vote of a two-thirds majority of the members of the Board shall be necessary to approve a variance from a use of land through a hardship relief petition as set forth in Article IV, Division 7, of this chapter.\n\nrequired_votes(Decision, Required) :-\n  decision_by(Decision, DetroitBZA),\n  matter_kind(Decision, Kind),\n  ordinary_bza_matter(Kind),\n  not matter_kind(Decision, HardshipReliefUseVariance),\n  authorized_members(DetroitBZA, Members),\n  Required = floor_div(Members, 2) + 1.\n\nrequired_votes(Decision, Required) :-\n  decision_by(Decision, DetroitBZA),\n  matter_kind(Decision, HardshipReliefUseVariance),\n  authorized_members(DetroitBZA, Members),\n  Required = ceil_div(2 * Members, 3).\n\nsufficient_concurrence(Decision) :-\n  required_votes(Decision, Required),\n  concurring_votes(Decision, Actual),\n  Actual >= Required.\n\nordinary_bza_matter(ReverseOrAdjustAdministrativeAction).\nordinary_bza_matter(ApplicantFavorableMatter).\nordinary_bza_matter(Variance).\n"
          }
        }
      },
      "test_result": {
        "passed": true,
        "tests": [
          "o1_r1",
          "o1_r2",
          "o1_r3",
          "o2_r1",
          "o2_r2",
          "o2_r3",
          "o3_r1",
          "o3_r2",
          "o3_r3",
          "rounding_is_defined_for_other_board_sizes"
        ],
        "count": 10,
        "failure": ""
      }
    },
    {
      "id": "finality",
      "citation": "\u00a750-2-79",
      "title": "Decision finality",
      "pressure": "Events, business calendars, evidence, and a conjunctive exception",
      "crate": "decision_finality",
      "sources": {
        "ontologies": {
          "o1": {
            "path": "decision_finality/ontology.sdmlish",
            "text": "module detroit_bza_decision_finality is\n  concept DecisionMakingBody\n  concept BoardDecision\n  concept BoardVote\n  concept NecessityFinding\n  concept RecordCertification\n  individual DetroitBZA is DecisionMakingBody\n  relation decision_by is from BoardDecision to DecisionMakingBody end\n  relation rendered_by_vote is from BoardDecision to BoardVote end\n  relation finding_for is from NecessityFinding to BoardDecision end\n  relation certified_by is from NecessityFinding to RecordCertification end\n  measure occurred_at is for BoardVote value LocalDateTime end\nend\n"
          },
          "o2": {
            "path": "decision_finality/ontology.manchester",
            "text": "Ontology: DetroitBzaDecisionFinality\nClass: DecisionMakingBody\nClass: BoardDecision\nClass: BoardVote\nClass: NecessityFinding\nClass: RecordCertification\nIndividual: DetroitBZA\n  Types: DecisionMakingBody\nObjectProperty: decidedBy\n  Domain: BoardDecision\n  Range: DecisionMakingBody\nObjectProperty: renderedByVote\n  Domain: BoardDecision\n  Range: BoardVote\nObjectProperty: findingFor\n  Domain: NecessityFinding\n  Range: BoardDecision\nObjectProperty: certifiedBy\n  Domain: NecessityFinding\n  Range: RecordCertification\nDataProperty: occurredAt\n  Domain: BoardVote\n  Range: LocalDateTime\n"
          },
          "o3": {
            "path": "decision_finality/ontology.zonto",
            "text": "prefix detroit https://detroitmi.gov/zoning/\nclass DecisionMakingBody\nclass BoardDecision\nclass BoardVote\nclass NecessityFinding\nclass RecordCertification\nindividual DetroitBZA types DecisionMakingBody\nproperty decision_by domain BoardDecision range DecisionMakingBody min 1 max 1\nproperty rendered_by_vote domain BoardDecision range BoardVote min 1 max 1\nproperty finding_for domain NecessityFinding range BoardDecision\nproperty certified_by domain NecessityFinding range RecordCertification\ndatatype occurred_at domain BoardVote range LocalDateTime min 1 max 1\n"
          }
        },
        "rules": {
          "r1": {
            "path": "decision_finality/rule.provision",
            "text": "module detroit_bza_decision_finality\nimport detroit_bza_decision_finality\nprovision ordinary_finality\n  id \"detroit:article-ii:section-50-2-79:ordinary-finality\"\n  source \"\u00a750-2-79\" quote \"Decisions that are rendered by the Board of Zoning Appeals shall not become final until 4:00 p.m. on the third business day after the vote,\"\n  if decision_by(decision, DetroitBZA) && rendered_by_vote(decision, vote) && !certified_immediate_effect(decision)\n  require final_at(decision) == at_time(add_business_days(date(occurred_at(vote)), 3), 16:00)\nend\nprovision certified_immediate_effect\n  id \"detroit:article-ii:section-50-2-79:immediate-effect-exception\"\n  source \"\u00a750-2-79 exception\" quote \"unless the Board finds the immediate effect of such order necessary for the preservation of property or personal rights and so certifies on the record.\"\n  overrides ordinary_finality\n  if decision_by(decision, DetroitBZA) && finding_for(finding, decision) && necessary_to_preserve(finding, PropertyRights || PersonalRights) && certified_by(finding, record_certification)\n  require final_at(decision) == occurred_at(vote_rendering(decision))\nend\n"
          },
          "r2": {
            "path": "decision_finality/rule.labeled",
            "text": "RuleModule: DetroitBzaDecisionFinality\nImportOntology: DetroitBzaDecisionFinality\nProvision: OrdinaryFinality\n  PropositionId: detroit:article-ii:section-50-2-79:ordinary-finality\n  SourceSpan: ordinary | Decisions that are rendered by the Board of Zoning Appeals shall not become final until 4:00 p.m. on the third business day after the vote,\n  AppliesWhen: (decidedBy(decision, DetroitBZA) && renderedByVote(decision, vote) && !CertifiedImmediateEffect(decision))\n  FinalAt: atTime(addBusinessDays(date(occurredAt(vote)), 3), 16:00)\nProvision: CertifiedImmediateEffect\n  PropositionId: detroit:article-ii:section-50-2-79:immediate-effect-exception\n  SourceSpan: exception | unless the Board finds the immediate effect of such order necessary for the preservation of property or personal rights and so certifies on the record.\n  Overrides: OrdinaryFinality\n  AppliesWhen: (decidedBy(decision, DetroitBZA) && findingFor(finding, decision) && necessaryToPreserve(finding, PropertyRights || PersonalRights) && certifiedBy(finding, recordCertification))\n  FinalAt: occurredAt(voteRendering(decision))\n"
          },
          "r3": {
            "path": "decision_finality/rule.datalog",
            "text": "module detroit.bza_decision_finality\nimport ontology.zonto\nsource ordinary id detroit:article-ii:section-50-2-79:ordinary-finality | Decisions that are rendered by the Board of Zoning Appeals shall not become final until 4:00 p.m. on the third business day after the vote,\nsource exception id detroit:article-ii:section-50-2-79:immediate-effect-exception | unless the Board finds the immediate effect of such order necessary for the preservation of property or personal rights and so certifies on the record.\nfinal_at(Decision, FinalAt) :- decision_by(Decision, DetroitBZA), rendered_by_vote(Decision, Vote), occurred_at(Vote, VotedAt), not immediate_effect_authorized(Decision), FinalAt = at_time(add_business_days(date(VotedAt), 3), 16:00).\nimmediate_effect_authorized(Decision) :- finding_for(Finding, Decision), necessary_to_preserve(Finding, PropertyRights), certified_by(Finding, Certification).\nimmediate_effect_authorized(Decision) :- finding_for(Finding, Decision), necessary_to_preserve(Finding, PersonalRights), certified_by(Finding, Certification).\nfinal_at(Decision, VotedAt) :- decision_by(Decision, DetroitBZA), rendered_by_vote(Decision, Vote), occurred_at(Vote, VotedAt), immediate_effect_authorized(Decision).\n"
          }
        }
      },
      "test_result": {
        "passed": true,
        "tests": [
          "o1_r1",
          "o1_r2",
          "o1_r3",
          "o2_r1",
          "o2_r2",
          "o2_r3",
          "o3_r1",
          "o3_r2",
          "o3_r3"
        ],
        "count": 9,
        "failure": ""
      }
    },
    {
      "id": "lapse",
      "citation": "\u00a750-3-386",
      "title": "Approval lapse and extension",
      "pressure": "Automatic state transition, bounded power, history, and precedence",
      "crate": "approval_lapse",
      "sources": {
        "ontologies": {
          "o1": {
            "path": "approval_lapse/ontology.sdmlish",
            "text": "module detroit_regulated_use_grants is\n  concept RegulatedUseGrant\n  concept RegulatedUse\n  concept Permit\n  concept Extension\n  concept Application\n  concept PublicHearing\n  concept DecisionMakingBody\n  relation grant_for is from RegulatedUseGrant to RegulatedUse end\n  relation permit_under is from Permit to RegulatedUseGrant end\n  relation extension_of is from Extension to RegulatedUseGrant end\n  relation authorized_by is from Extension to DecisionMakingBody end\n  relation new_application_for is from Application to RegulatedUse end\n  relation hearing_for is from PublicHearing to Application end\n  measure granted_at is for RegulatedUseGrant value LocalDate end\n  measure obtained_at is for Permit value LocalDate end\n  measure extended_until is for Extension value LocalDate end\n  predicate unlawfully_established_or_expanded(RegulatedUse)\n  predicate legalized_by_regulated_use_hearing(RegulatedUse)\nend\n"
          },
          "o2": {
            "path": "approval_lapse/ontology.manchester",
            "text": "Ontology: DetroitRegulatedUseGrants\nClass: RegulatedUseGrant\nClass: RegulatedUse\nClass: Permit\nClass: Extension\nClass: Application\nClass: PublicHearing\nClass: DecisionMakingBody\nObjectProperty: grantFor\n  Domain: RegulatedUseGrant\n  Range: RegulatedUse\nObjectProperty: permitUnder\n  Domain: Permit\n  Range: RegulatedUseGrant\nObjectProperty: extensionOf\n  Domain: Extension\n  Range: RegulatedUseGrant\nObjectProperty: authorizedBy\n  Domain: Extension\n  Range: DecisionMakingBody\nObjectProperty: newApplicationFor\n  Domain: Application\n  Range: RegulatedUse\nObjectProperty: hearingFor\n  Domain: PublicHearing\n  Range: Application\nDataProperty: grantedAt\n  Domain: RegulatedUseGrant\n  Range: LocalDate\nDataProperty: obtainedAt\n  Domain: Permit\n  Range: LocalDate\nDataProperty: extendedUntil\n  Domain: Extension\n  Range: LocalDate\n"
          },
          "o3": {
            "path": "approval_lapse/ontology.zonto",
            "text": "prefix detroit https://detroitmi.gov/zoning/\nclass RegulatedUseGrant\nclass RegulatedUse\nclass Permit\nclass Extension\nclass Application\nclass PublicHearing\nclass DecisionMakingBody\nproperty grant_for domain RegulatedUseGrant range RegulatedUse min 1 max 1\nproperty permit_under domain Permit range RegulatedUseGrant\nproperty extension_of domain Extension range RegulatedUseGrant min 1 max 1\nproperty authorized_by domain Extension range DecisionMakingBody min 1 max 1\nproperty new_application_for domain Application range RegulatedUse\nproperty hearing_for domain PublicHearing range Application\ndatatype granted_at domain RegulatedUseGrant range LocalDate min 1 max 1\ndatatype obtained_at domain Permit range LocalDate min 1 max 1\ndatatype extended_until domain Extension range LocalDate min 1 max 1\npredicate unlawfully_established_or_expanded domain RegulatedUse\npredicate legalized_by_regulated_use_hearing domain RegulatedUse\n"
          }
        },
        "rules": {
          "r1": {
            "path": "approval_lapse/rule.provision",
            "text": "module detroit_regulated_use_grant_lapse\nimport detroit_regulated_use_grants\nprovision lapse_without_permit\n  id \"detroit:article-iii:section-50-3-386:lapse\"\n  source \"\u00a750-3-386 sentence 1\" quote \"In any case where a permit for a regulated use has not been obtained within six months after the granting of said use, the grant shall be null and void without further action\"\n  if !exists permit: permit_under(permit, grant) && obtained_at(permit) <= add_calendar_months(granted_at(grant), 6) && !valid_extension(grant)\n  require status_at(grant, add_calendar_months(granted_at(grant), 6)) == NullAndVoid\nend\nprovision one_bounded_extension\n  id \"detroit:article-iii:section-50-3-386:extension\"\n  source \"\u00a750-3-386 sentence 1 exception\" quote \"except, that the Buildings, Safety Engineering, and Environmental Department or, where applicable, the Board of Zoning Appeals may extend, without further public hearing, said six-month deadline for no more than 12 months beyond the expiration date of the original six months.\"\n  if extension_of(extension, grant) && authorized_by(extension, BSEED || DetroitBZA) && extended_until(extension) <= add_calendar_months(granted_at(grant), 18) && !extension_barred(grant)\n  permit valid_extension(grant)\nend\nprovision extension_bar\n  id \"detroit:article-iii:section-50-3-386:notwithstanding\"\n  source \"\u00a750-3-386 final sentence\" quote \"Notwithstanding the preceding, no such extension may be considered in the case of a land use that was unlawfully established or expanded and that was subsequently legalized as a result of a regulated land use hearing.\"\n  overrides one_bounded_extension\n  if grant_for(grant, use) && unlawfully_established_or_expanded(use) && legalized_by_regulated_use_hearing(use)\n  prohibit valid_extension(grant)\nend\nprovision no_additional_extension\n  id \"detroit:article-iii:section-50-3-386:no-additional-extension\"\n  source \"\u00a750-3-386 sentence 2\" quote \"Where this extension expires, no additional extension shall be authorized, unless a new application has been filed and a further public hearing has been held.\"\n  if expired(extension) && extension_of(extension, grant)\n  prohibit additional_extension(grant)\n  permit proceed_as_new_application(use) if new_application_for(application, use) && hearing_for(hearing, application)\nend\n"
          },
          "r2": {
            "path": "approval_lapse/rule.labeled",
            "text": "RuleModule: DetroitRegulatedUseGrantLapse\nImportOntology: DetroitRegulatedUseGrants\nProvision: LapseWithoutPermit\n  PropositionId: detroit:article-iii:section-50-3-386:lapse\n  SourceSpan: lapse | In any case where a permit for a regulated use has not been obtained within six months after the granting of said use, the grant shall be null and void without further action\n  AppliesWhen: (!exists permit: permitUnder(permit, grant) && obtainedAt(permit) <= addCalendarMonths(grantedAt(grant), 6) && !ValidExtension(grant))\n  StateTransition: grant -> NullAndVoid at addCalendarMonths(grantedAt(grant), 6)\nProvision: OneBoundedExtension\n  PropositionId: detroit:article-iii:section-50-3-386:extension\n  SourceSpan: exception | except, that the Buildings, Safety Engineering, and Environmental Department or, where applicable, the Board of Zoning Appeals may extend, without further public hearing, said six-month deadline for no more than 12 months beyond the expiration date of the original six months.\n  AppliesWhen: (extensionOf(extension, grant) && authorizedBy(extension, BSEED || DetroitBZA) && extendedUntil(extension) <= addCalendarMonths(grantedAt(grant), 18) && !ExtensionBar(grant))\n  Power: authorize ValidExtension(grant)\nProvision: ExtensionBar\n  PropositionId: detroit:article-iii:section-50-3-386:notwithstanding\n  SourceSpan: precedence | Notwithstanding the preceding, no such extension may be considered in the case of a land use that was unlawfully established or expanded and that was subsequently legalized as a result of a regulated land use hearing.\n  Overrides: OneBoundedExtension\n  AppliesWhen: (grantFor(grant, use) && unlawfullyEstablishedOrExpanded(use) && legalizedByRegulatedUseHearing(use))\n  Prohibition: ValidExtension(grant)\nProvision: NoAdditionalExtension\n  PropositionId: detroit:article-iii:section-50-3-386:no-additional-extension\n  SourceSpan: renewal | Where this extension expires, no additional extension shall be authorized, unless a new application has been filed and a further public hearing has been held.\n  AppliesWhen: (expired(extension) && extensionOf(extension, grant))\n  Prohibition: AdditionalExtension(grant)\n  AlternativeProcedure: ProceedAsNewApplication(use) when (newApplicationFor(application, use) && hearingFor(hearing, application))\n"
          },
          "r3": {
            "path": "approval_lapse/rule.datalog",
            "text": "module detroit.regulated_use_grant_lapse\nimport ontology.zonto\nsource lapse id detroit:article-iii:section-50-3-386:lapse\nsource extension id detroit:article-iii:section-50-3-386:extension\nsource precedence id detroit:article-iii:section-50-3-386:notwithstanding\nsource renewal id detroit:article-iii:section-50-3-386:no-additional-extension\nextension_barred(Grant) :- grant_for(Grant, Use), unlawfully_established_or_expanded(Use), legalized_by_regulated_use_hearing(Use).\nvalid_extension(Grant, ExtendedUntil) :- extension_of(Extension, Grant), authorized_by(Extension, Authority), extension_authority(Authority), extended_until(Extension, ExtendedUntil), granted_at(Grant, GrantedAt), ExtendedUntil <= add_calendar_months(GrantedAt, 18), not extension_barred(Grant).\neffective_deadline(Grant, ExtendedUntil) :- valid_extension(Grant, ExtendedUntil).\neffective_deadline(Grant, InitialDeadline) :- granted_at(Grant, GrantedAt), InitialDeadline = add_calendar_months(GrantedAt, 6), not valid_extension(Grant, _).\nnull_and_void_at(Grant, Deadline) :- effective_deadline(Grant, Deadline), not permit_obtained_by(Grant, Deadline).\npermit_obtained_by(Grant, Deadline) :- permit_under(Permit, Grant), obtained_at(Permit, ObtainedAt), ObtainedAt <= Deadline.\nextension_authority(BSEED).\nextension_authority(DetroitBZA).\nadditional_extension_prohibited(Grant) :- extension_of(Extension, Grant), expired(Extension).\nmay_proceed_as_new_application(Use) :- new_application_for(Application, Use), hearing_for(Hearing, Application).\n"
          }
        }
      },
      "test_result": {
        "passed": true,
        "tests": [
          "o1_r1",
          "o1_r2",
          "o1_r3",
          "o2_r1",
          "o2_r2",
          "o2_r3",
          "o3_r1",
          "o3_r2",
          "o3_r3"
        ],
        "count": 9,
        "failure": ""
      }
    },
    {
      "id": "eligibility",
      "citation": "\u00a750-3-341",
      "title": "Eligibility and spacing",
      "pressure": "Independent exceptions, identity-aware spatial counting, and waiver",
      "crate": "regulated_use_eligibility",
      "sources": {
        "ontologies": {
          "o1": {
            "path": "regulated_use_eligibility/ontology.sdmlish",
            "text": "module detroit_regulated_use_eligibility is\n  concept Applicant\n  concept RegulatedUseApplication\n  concept Property\n  concept DelinquentObligation\n  concept BlightViolation\n  concept RegulatedUseSite\n  concept SpacingWaiver\n  relation filed_by is from RegulatedUseApplication to Applicant end\n  relation concerns_property is from RegulatedUseApplication to Property end\n  relation delinquent_on is from Applicant to DelinquentObligation end\n  relation obligation_from is from DelinquentObligation to BlightViolation end\n  relation acquired_by_foreclosure_or_deed_in_lieu is from Applicant to Property end\n  relation authorization_corrects is from RegulatedUseApplication to BlightViolation end\n  relation waiver_for is from SpacingWaiver to RegulatedUseApplication end\n  measure boundary_distance_to is for RegulatedUseApplication, RegulatedUseSite value Length end\n  predicate legally_established(RegulatedUseSite)\nend\n"
          },
          "o2": {
            "path": "regulated_use_eligibility/ontology.manchester",
            "text": "Ontology: DetroitRegulatedUseEligibility\nClass: Applicant\nClass: RegulatedUseApplication\nClass: Property\nClass: DelinquentObligation\nClass: BlightViolation\nClass: RegulatedUseSite\nClass: SpacingWaiver\nObjectProperty: filedBy\n  Domain: RegulatedUseApplication\n  Range: Applicant\nObjectProperty: concernsProperty\n  Domain: RegulatedUseApplication\n  Range: Property\nObjectProperty: delinquentOn\n  Domain: Applicant\n  Range: DelinquentObligation\nObjectProperty: obligationFrom\n  Domain: DelinquentObligation\n  Range: BlightViolation\nObjectProperty: acquiredByForeclosureOrDeedInLieu\n  Domain: Applicant\n  Range: Property\nObjectProperty: authorizationCorrects\n  Domain: RegulatedUseApplication\n  Range: BlightViolation\nObjectProperty: waiverFor\n  Domain: SpacingWaiver\n  Range: RegulatedUseApplication\nDataProperty: boundaryDistanceTo\n  Domain: RegulatedUseApplication\n  Range: Length\n"
          },
          "o3": {
            "path": "regulated_use_eligibility/ontology.zonto",
            "text": "prefix detroit https://detroitmi.gov/zoning/\nclass Applicant\nclass RegulatedUseApplication\nclass Property\nclass DelinquentObligation\nclass BlightViolation\nclass RegulatedUseSite\nclass SpacingWaiver\nproperty filed_by domain RegulatedUseApplication range Applicant min 1 max 1\nproperty concerns_property domain RegulatedUseApplication range Property min 1 max 1\nproperty delinquent_on domain Applicant range DelinquentObligation\nproperty obligation_from domain DelinquentObligation range BlightViolation min 1 max 1\nproperty acquired_by_foreclosure_or_deed_in_lieu domain Applicant range Property\nproperty authorization_corrects domain RegulatedUseApplication range BlightViolation\nproperty waiver_for domain SpacingWaiver range RegulatedUseApplication\ndatatype boundary_distance_to domain RegulatedUseApplication target RegulatedUseSite range Length\npredicate legally_established domain RegulatedUseSite\n"
          }
        },
        "rules": {
          "r1": {
            "path": "regulated_use_eligibility/rule.provision",
            "text": "module detroit_regulated_use_eligibility\nimport detroit_regulated_use_eligibility\nprovision delinquent_applicant_ineligible\n  id \"detroit:article-iii:section-50-3-341:b:ineligibility\"\n  source \"\u00a750-3-341(b)\" quote \"a person is ineligible to apply for a regulated use where the person is delinquent in paying a civil fine, costs, or a justice system assessment imposed by the Blight Administrative Hearings Bureau\"\n  if filed_by(application, applicant) && delinquent_on(applicant, obligation) && obligation_from(obligation, violation) && !eligibility_exception(application, applicant, violation)\n  prohibit eligible_to_apply(applicant, application)\nend\nprovision eligibility_exceptions\n  id \"detroit:article-iii:section-50-3-341:b:exceptions\"\n  source \"\u00a750-3-341(b) exceptions\" quote \"This ineligibility does not apply to an applicant for a zoning authorization if the applicant became the owner of the property by foreclosure or by taking a deed in lieu of foreclosure ... Further, this ineligibility does not apply if the zoning authorization will correct, in whole or in part, the blight violation that was the subject of the delinquent payment.\"\n  if (concerns_property(application, property) && acquired_by_foreclosure_or_deed_in_lieu(applicant, property)) || authorization_corrects(application, violation)\n  permit eligibility_exception(application, applicant, violation)\nend\nprovision regulated_use_spacing\n  id \"detroit:article-iii:section-50-3-341:c:spacing\"\n  source \"\u00a750-3-341(c)\" quote \"shall not approve any such request where there are already in existence two or more regulated uses within 1,000 feet of the boundaries of the site of the proposed regulated use, except as provided for through the waiver provisions\"\n  if count distinct site where legally_established(site) && boundary_distance_to(application, site) <= 1000 ft >= 2 && !exists waiver: waiver_for(waiver, application)\n  prohibit approve(application)\nend\n"
          },
          "r2": {
            "path": "regulated_use_eligibility/rule.labeled",
            "text": "RuleModule: DetroitRegulatedUseEligibility\nImportOntology: DetroitRegulatedUseEligibility\nProvision: DelinquentApplicantIneligible\n  PropositionId: detroit:article-iii:section-50-3-341:b:ineligibility\n  SourceSpan: ineligibility | a person is ineligible to apply for a regulated use where the person is delinquent in paying a civil fine, costs, or a justice system assessment imposed by the Blight Administrative Hearings Bureau\n  AppliesWhen: (filedBy(application, applicant) && delinquentOn(applicant, obligation) && obligationFrom(obligation, violation) && !EligibilityException(application, applicant, violation))\n  Prohibition: EligibleToApply(applicant, application)\nProvision: EligibilityExceptions\n  PropositionId: detroit:article-iii:section-50-3-341:b:exceptions\n  SourceSpan: exceptions | This ineligibility does not apply to an applicant for a zoning authorization if the applicant became the owner of the property by foreclosure or by taking a deed in lieu of foreclosure ... Further, this ineligibility does not apply if the zoning authorization will correct, in whole or in part, the blight violation that was the subject of the delinquent payment.\n  AppliesWhen: ((concernsProperty(application, property) && acquiredByForeclosureOrDeedInLieu(applicant, property)) || authorizationCorrects(application, violation))\n  Effect: EligibilityException(application, applicant, violation)\nProvision: RegulatedUseSpacing\n  PropositionId: detroit:article-iii:section-50-3-341:c:spacing\n  SourceSpan: spacing | shall not approve any such request where there are already in existence two or more regulated uses within 1,000 feet of the boundaries of the site of the proposed regulated use, except as provided for through the waiver provisions\n  AppliesWhen: (count distinct site where (legallyEstablished(site) && boundaryDistanceTo(application, site) <= 1000 ft) >= 2 && !exists waiver: waiverFor(waiver, application))\n  Prohibition: Approve(application)\n"
          },
          "r3": {
            "path": "regulated_use_eligibility/rule.datalog",
            "text": "module detroit.regulated_use_eligibility\nimport ontology.zonto\nsource ineligibility id detroit:article-iii:section-50-3-341:b:ineligibility | a person is ineligible to apply for a regulated use where the person is delinquent in paying a civil fine, costs, or a justice system assessment imposed by the Blight Administrative Hearings Bureau\nsource exceptions id detroit:article-iii:section-50-3-341:b:exceptions | This ineligibility does not apply to an applicant for a zoning authorization if the applicant became the owner of the property by foreclosure or by taking a deed in lieu of foreclosure ... Further, this ineligibility does not apply if the zoning authorization will correct, in whole or in part, the blight violation that was the subject of the delinquent payment.\nsource spacing id detroit:article-iii:section-50-3-341:c:spacing | shall not approve any such request where there are already in existence two or more regulated uses within 1,000 feet of the boundaries of the site of the proposed regulated use, except as provided for through the waiver provisions\neligibility_exception(Application, Applicant, Violation) :- concerns_property(Application, Property), acquired_by_foreclosure_or_deed_in_lieu(Applicant, Property).\neligibility_exception(Application, Applicant, Violation) :- authorization_corrects(Application, Violation), filed_by(Application, Applicant).\nineligible(Applicant, Application) :- filed_by(Application, Applicant), delinquent_on(Applicant, Obligation), obligation_from(Obligation, Violation), not eligibility_exception(Application, Applicant, Violation).\nnearby_regulated_count(Application, count_distinct<Site>) :- legally_established(Site), boundary_distance_to(Application, Site, Distance), Distance <= 1000 ft.\napproval_prohibited(Application) :- nearby_regulated_count(Application, Count), Count >= 2, not waiver_for(_, Application).\n"
          }
        }
      },
      "test_result": {
        "passed": true,
        "tests": [
          "o1_r1",
          "o1_r2",
          "o1_r3",
          "o2_r1",
          "o2_r2",
          "o2_r3",
          "o3_r1",
          "o3_r2",
          "o3_r3"
        ],
        "count": 9,
        "failure": ""
      }
    },
    {
      "id": "waiver",
      "citation": "\u00a750-3-443",
      "title": "Controlled-use waiver",
      "pressure": "Discretion, hard constraint, and unresolved source coordination",
      "crate": "controlled_use_waiver",
      "sources": {
        "ontologies": {
          "o1": {
            "path": "controlled_use_waiver/ontology.sdmlish",
            "text": "module detroit_controlled_use_waiver is\n  concept ControlledUseProposal\n  concept ZoningDistrict\n  concept NeighborhoodShoppingCenter\n  concept CommercialEstablishment\n  concept ImprovementFinding\n  concept PlanningDirector\n  relation located_in_district is from ControlledUseProposal to ZoningDistrict end\n  relation located_in_center is from ControlledUseProposal to NeighborhoodShoppingCenter end\n  relation establishment_in is from CommercialEstablishment to NeighborhoodShoppingCenter end\n  relation finding_for is from ImprovementFinding to ControlledUseProposal end\n  relation determined_and_documented_by is from ImprovementFinding to PlanningDirector end\n  measure usable_retail_area is for NeighborhoodShoppingCenter value Area end\n  measure gross_floor_area is for NeighborhoodShoppingCenter value Area end\n  measure private_off_street_parking_spaces is for NeighborhoodShoppingCenter value WholeCount end\n  predicate permitted_by_right(ControlledUseProposal, ZoningDistrict)\n  predicate conditionally_permitted(ControlledUseProposal, ZoningDistrict)\n  predicate only_controlled_use_in_center(ControlledUseProposal, NeighborhoodShoppingCenter)\nend\n"
          },
          "o2": {
            "path": "controlled_use_waiver/ontology.manchester",
            "text": "Ontology: DetroitControlledUseWaiver\nClass: ControlledUseProposal\nClass: ZoningDistrict\nClass: NeighborhoodShoppingCenter\nClass: CommercialEstablishment\nClass: ImprovementFinding\nClass: PlanningDirector\nObjectProperty: locatedInDistrict\n  Domain: ControlledUseProposal\n  Range: ZoningDistrict\nObjectProperty: locatedInCenter\n  Domain: ControlledUseProposal\n  Range: NeighborhoodShoppingCenter\nObjectProperty: establishmentIn\n  Domain: CommercialEstablishment\n  Range: NeighborhoodShoppingCenter\nObjectProperty: findingFor\n  Domain: ImprovementFinding\n  Range: ControlledUseProposal\nObjectProperty: determinedAndDocumentedBy\n  Domain: ImprovementFinding\n  Range: PlanningDirector\nDataProperty: usableRetailArea\n  Domain: NeighborhoodShoppingCenter\n  Range: Area\nDataProperty: grossFloorArea\n  Domain: NeighborhoodShoppingCenter\n  Range: Area\nDataProperty: privateOffStreetParkingSpaces\n  Domain: NeighborhoodShoppingCenter\n  Range: nonNegativeInteger\n"
          },
          "o3": {
            "path": "controlled_use_waiver/ontology.zonto",
            "text": "prefix detroit https://detroitmi.gov/zoning/\nclass ControlledUseProposal\nclass ZoningDistrict\nclass NeighborhoodShoppingCenter\nclass CommercialEstablishment\nclass ImprovementFinding\nclass PlanningDirector\nproperty located_in_district domain ControlledUseProposal range ZoningDistrict\nproperty located_in_center domain ControlledUseProposal range NeighborhoodShoppingCenter\nproperty establishment_in domain CommercialEstablishment range NeighborhoodShoppingCenter\nproperty finding_for domain ImprovementFinding range ControlledUseProposal\nproperty determined_and_documented_by domain ImprovementFinding range PlanningDirector\ndatatype usable_retail_area domain NeighborhoodShoppingCenter range Area\ndatatype gross_floor_area domain NeighborhoodShoppingCenter range Area\ndatatype private_off_street_parking_spaces domain NeighborhoodShoppingCenter range nonNegativeInteger\npredicate permitted_by_right domain ControlledUseProposal target ZoningDistrict\npredicate conditionally_permitted domain ControlledUseProposal target ZoningDistrict\npredicate only_controlled_use_in_center domain ControlledUseProposal target NeighborhoodShoppingCenter\n"
          }
        },
        "rules": {
          "r1": {
            "path": "controlled_use_waiver/rule.provision",
            "text": "module detroit_controlled_use_waiver\nimport detroit_controlled_use_waiver\nprovision district_permission_bar\n  id \"detroit:article-iii:section-50-3-443:district-bar\"\n  source \"\u00a750-3-443 exception\" quote \"except, that as provided for in Section 50-15-30 of this Code, in no case shall a controlled use be established in any zoning district where such a use is not permitted by right or as a conditional use\"\n  if located_in_district(proposal, district) && !(permitted_by_right(proposal, district) || conditionally_permitted(proposal, district))\n  prohibit grant_spacing_waiver(proposal)\nend\nprovision spacing_waiver_findings\n  id \"detroit:article-iii:section-50-3-443:findings\"\n  source \"\u00a750-3-443 lead-in\" quote \"may be waived, provided, that any one of the following findings is made\"\n  source \"\u00a750-3-443 list join\" quote \"; and (2)\"\n  coordination unresolved {\n    lead_in any_one\n    terminal_join and\n  }\n  candidate finding_1 if only_controlled_use_in_center(proposal, center) && count distinct establishment where establishment_in(establishment, center) >= 2 && usable_retail_area(center) >= 50000 sq_ft && private_off_street_parking_spaces(center) >= ceil(gross_floor_area(center) / 200 sq_ft)\n  candidate finding_2 if finding_for(finding, proposal) && contributes_to(finding, Social || Economic || Aesthetic || PhysicalImprovement) && determined_and_documented_by(finding, PlanningDirector)\n  require !district_permission_bar(proposal)\nend\n"
          },
          "r2": {
            "path": "controlled_use_waiver/rule.labeled",
            "text": "RuleModule: DetroitControlledUseWaiver\nImportOntology: DetroitControlledUseWaiver\nProvision: DistrictPermissionBar\n  PropositionId: detroit:article-iii:section-50-3-443:district-bar\n  AppliesWhen: (locatedInDistrict(proposal, district) && !(permittedByRight(proposal, district) || conditionallyPermitted(proposal, district)))\n  Prohibition: GrantSpacingWaiver(proposal)\nProvision: SpacingWaiverFindings\n  PropositionId: detroit:article-iii:section-50-3-443:findings\n  SourceSpan: lead-in | may be waived, provided, that any one of the following findings is made\n  SourceSpan: terminal-join | ; and (2)\n  CoordinationStatus: Unresolved\n  LeadInOperator: AnyOne\n  TerminalJoinOperator: And\n  CandidateFinding: CenterQualification when (onlyControlledUseInCenter(proposal, center) && count distinct establishment where establishmentIn(establishment, center) >= 2 && usableRetailArea(center) >= 50000 sq_ft && privateOffStreetParkingSpaces(center) >= ceil(grossFloorArea(center) / 200 sq_ft))\n  CandidateFinding: DocumentedImprovement when (findingFor(finding, proposal) && contributesTo(finding, Social || Economic || Aesthetic || PhysicalImprovement) && determinedAndDocumentedBy(finding, PlanningDirector))\n  SubjectTo: !DistrictPermissionBar(proposal)\n"
          },
          "r3": {
            "path": "controlled_use_waiver/rule.datalog",
            "text": "module detroit.controlled_use_waiver\nimport ontology.zonto\nsource district_bar id detroit:article-iii:section-50-3-443:district-bar\nsource lead_in id detroit:article-iii:section-50-3-443:findings | may be waived, provided, that any one of the following findings is made\nsource terminal_join id detroit:article-iii:section-50-3-443:findings | ; and (2)\ncoordination_signal(findings, lead_in, any_one).\ncoordination_signal(findings, terminal_join, and).\ncoordination_status(findings, unresolved).\ndistrict_permission_bar(Proposal) :- located_in_district(Proposal, District), not permitted_by_right(Proposal, District), not conditionally_permitted(Proposal, District).\ncandidate_finding(Proposal, center_qualification) :- only_controlled_use_in_center(Proposal, Center), establishment_count(Center, Count), Count >= 2, usable_retail_area(Center, Area), Area >= 50000 sq_ft, gross_floor_area(Center, Gfa), private_off_street_parking_spaces(Center, Parking), Parking >= ceil_div(Gfa, 200 sq_ft).\ncandidate_finding(Proposal, documented_improvement) :- finding_for(Finding, Proposal), contributes_to(Finding, Improvement), qualifying_improvement(Improvement), determined_and_documented_by(Finding, PlanningDirector).\nestablishment_count(Center, count_distinct<Establishment>) :- establishment_in(Establishment, Center).\nqualifying_improvement(Social). qualifying_improvement(Economic). qualifying_improvement(Aesthetic). qualifying_improvement(PhysicalImprovement).\n"
          }
        }
      },
      "test_result": {
        "passed": true,
        "tests": [
          "o1_r1",
          "o1_r2",
          "o1_r3",
          "o2_r1",
          "o2_r2",
          "o2_r3",
          "o3_r1",
          "o3_r2",
          "o3_r3"
        ],
        "count": 9,
        "failure": ""
      }
    }
  ]
};
