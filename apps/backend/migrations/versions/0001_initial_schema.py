"""Initial AP-RKB scaffold schema (frozen DDL)."""

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

UPGRADE_SQL = [
    (
        "\nCREATE TABLE licenses (\n\tcode VARCHAR(64) NOT NULL, \n\tname VARCHAR(255)"
        " NOT NULL, \n\tallows_mining BOOLEAN NOT NULL, \n\tallows_display BOOLEAN NO"
        "T NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAUL"
        "T now() NOT NULL, \n\tcreated_by UUID, \n\tPRIMARY KEY (id), \n\tUNIQUE (code)"
        "\n)\n\n"
    ),
    (
        "\nCREATE TABLE api_clients (\n\tname VARCHAR(255) NOT NULL, \n\tkey_hash VARC"
        "HAR(255) NOT NULL, \n\tkey_prefix VARCHAR(32) NOT NULL, \n\trole VARCHAR(16)"
        " NOT NULL, \n\tis_active BOOLEAN NOT NULL, \n\tupdated_at TIMESTAMP WITH TIM"
        "E ZONE DEFAULT now() NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAM"
        "P WITH TIME ZONE DEFAULT now() NOT NULL, \n\tcreated_by UUID, \n\tPRIMARY KE"
        "Y (id), \n\tUNIQUE (key_hash)\n)\n\n"
    ),
    (
        "\nCREATE TABLE journal_profiles (\n\tname VARCHAR(255) NOT NULL, \n\tissn VAR"
        "CHAR(16), \n\tpublisher VARCHAR(255), \n\tfield VARCHAR(255), \n\tsubfield VAR"
        "CHAR(255), \n\tsimilar_journal_ids UUID[] NOT NULL, \n\tupdated_at TIMESTAMP"
        " WITH TIME ZONE DEFAULT now() NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at"
        " TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tcreated_by UUID, \n\tP"
        "RIMARY KEY (id), \n\tUNIQUE (issn)\n)\n\n"
    ),
    (
        "\nCREATE TABLE jobs (\n\ttype VARCHAR(64) NOT NULL, \n\tpayload JSONB NOT NUL"
        "L, \n\tstatus VARCHAR(16) NOT NULL, \n\tattempts INTEGER NOT NULL, \n\tlocked_"
        "at TIMESTAMP WITH TIME ZONE, \n\terror TEXT, \n\tupdated_at TIMESTAMP WITH T"
        "IME ZONE DEFAULT now() NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMEST"
        "AMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tcreated_by UUID, \n\tPRIMARY "
        "KEY (id)\n)\n\n"
    ),
    (
        "\nCREATE TABLE recommendation_logs (\n\trequest JSONB NOT NULL, \n\tresults J"
        "SONB NOT NULL, \n\tpolicy_versions JSONB NOT NULL, \n\tid UUID NOT NULL, \n\tc"
        "reated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tcreated_by "
        "UUID, \n\tPRIMARY KEY (id)\n)\n\n"
    ),
    (
        "\nCREATE TABLE taxonomy_releases (\n\tversion VARCHAR(32) NOT NULL, \n\tstatu"
        "s VARCHAR(16) NOT NULL, \n\tpublished_at TIMESTAMP WITH TIME ZONE, \n\tupdat"
        "ed_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tid UUID NOT NUL"
        "L, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tcreat"
        "ed_by UUID, \n\tPRIMARY KEY (id), \n\tUNIQUE (version)\n)\n\n"
    ),
    (
        "\nCREATE TABLE article_genres (\n\tcode VARCHAR(64) NOT NULL, \n\tname VARCHA"
        "R(255) NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZO"
        "NE DEFAULT now() NOT NULL, \n\tcreated_by UUID, \n\tPRIMARY KEY (id), \n\tUNIQ"
        "UE (code)\n)\n\n"
    ),
    (
        '\nCREATE TABLE ref_enums (\n\t"group" VARCHAR(64) NOT NULL, \n\tcode VARCHAR('
        '64) NOT NULL, \n\tlabel VARCHAR(255) NOT NULL, \n\t"order" INTEGER NOT NULL,'
        " \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now()"
        ' NOT NULL, \n\tcreated_by UUID, \n\tPRIMARY KEY (id), \n\tUNIQUE ("group", cod'
        "e)\n)\n\n"
    ),
    (
        "\nCREATE TABLE audit_events (\n\tactor_id UUID, \n\taction VARCHAR(128) NOT N"
        "ULL, \n\tentity_type VARCHAR(128) NOT NULL, \n\tentity_id UUID, \n\tbefore JSO"
        "NB, \n\tafter JSONB, \n\trequest_id VARCHAR(64) NOT NULL, \n\tid UUID NOT NULL"
        ", \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tcreate"
        "d_by UUID, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(actor_id) REFERENCES api_cl"
        "ients (id)\n)\n\n"
    ),
    (
        "\nCREATE TABLE articles (\n\tdoi VARCHAR(255), \n\ttitle TEXT, \n\tjournal_id U"
        "UID, \n\tgenre_id UUID, \n\tlicense_id UUID NOT NULL, \n\tblob_key VARCHAR(102"
        "4) NOT NULL, \n\tingest_status VARCHAR(32) NOT NULL, \n\t"
        "updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tid UUID NOT NULL, \n"
        "\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tcreated_b"
        "y UUID, \n\tPRIMARY KEY (id), \n\tUNIQUE (doi), \n\tFOREIGN KEY(journal_id) RE"
        "FERENCES journal_profiles (id), \n\tFOREIGN KEY(genre_id) REFERENCES artic"
        "le_genres (id), \n\tFOREIGN KEY(license_id) REFERENCES licenses (id)\n)\n\n"
    ),
    (
        "\nCREATE TABLE guideline_rules (\n\tjournal_id UUID NOT NULL, \n\trule_type V"
        "ARCHAR(64) NOT NULL, \n\tpayload JSONB NOT NULL, \n\tis_mandatory BOOLEAN NO"
        "T NULL, \n\tactive_from TIMESTAMP WITH TIME ZONE, \n\tactive_to TIMESTAMP WI"
        "TH TIME ZONE, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE "
        "DEFAULT now() NOT NULL, \n\tcreated_by UUID, \n\tPRIMARY KEY (id), \n\tFOREIGN"
        " KEY(journal_id) REFERENCES journal_profiles (id)\n)\n\n"
    ),
    (
        "\nCREATE TABLE journal_fingerprints (\n\tjournal_id UUID NOT NULL, \n\tgenre_"
        "id UUID NOT NULL, \n\tvector VECTOR(384) NOT NULL, \n\tcomputed_at TIMESTAMP"
        " WITH TIME ZONE, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZO"
        "NE DEFAULT now() NOT NULL, \n\tcreated_by UUID, \n\tPRIMARY KEY (id), \n\tFORE"
        "IGN KEY(journal_id) REFERENCES journal_profiles (id), \n\tFOREIGN KEY(genr"
        "e_id) REFERENCES article_genres (id)\n)\n\n"
    ),
    (
        "\nCREATE TABLE overrides (\n\tclient_id UUID NOT NULL, \n\tvalidation_id UUID"
        " NOT NULL, \n\trule_code VARCHAR(32) NOT NULL, \n\trationale TEXT NOT NULL, "
        "\n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() "
        "NOT NULL, \n\tcreated_by UUID, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(client_id"
        ") REFERENCES api_clients (id)\n)\n\n"
    ),
    (
        "\nCREATE TABLE sections (\n\tcode VARCHAR(64) NOT NULL, \n\tname VARCHAR(255)"
        ' NOT NULL, \n\t"order" INTEGER NOT NULL, \n\trelease_id UUID NOT NULL, \n\tid '
        "UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT N"
        "ULL, \n\tcreated_by UUID, \n\tPRIMARY KEY (id), \n\tUNIQUE (release_id, code),"
        " \n\tFOREIGN KEY(release_id) REFERENCES taxonomy_releases (id)\n)\n\n"
    ),
    (
        "\nCREATE TABLE article_sections (\n\tarticle_id UUID NOT NULL, \n\tsection_co"
        'de VARCHAR(64), \n\theading TEXT, \n\t"order" INTEGER NOT NULL, \n\tid UUID NO'
        "T NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\t"
        "created_by UUID, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(article_id) REFERENCE"
        "S articles (id)\n)\n\n"
    ),
    (
        "\nCREATE TABLE moves (\n\tcode VARCHAR(64) NOT NULL, \n\tname VARCHAR(255) NO"
        "T NULL, \n\tsection_id UUID NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIM"
        "ESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tcreated_by UUID, \n\tPRIMA"
        "RY KEY (id), \n\tUNIQUE (section_id, code), \n\tFOREIGN KEY(section_id) REFE"
        "RENCES sections (id)\n)\n\n"
    ),
    (
        "\nCREATE TABLE sentences (\n\tarticle_id UUID NOT NULL, \n\tarticle_section_i"
        "d UUID, \n\ttext TEXT NOT NULL, \n\tchar_start INTEGER NOT NULL, \n\tchar_end "
        "INTEGER NOT NULL, \n\tembedding VECTOR(384), \n\tid UUID NOT NULL, \n\tcreated"
        "_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tcreated_by UUID, "
        "\n\tPRIMARY KEY (id), \n\tFOREIGN KEY(article_id) REFERENCES articles (id), "
        "\n\tFOREIGN KEY(article_section_id) REFERENCES article_sections (id)\n)\n\n"
    ),
    (
        "\nCREATE TABLE steps (\n\tcode VARCHAR(64) NOT NULL, \n\tname VARCHAR(255) NO"
        "T NULL, \n\tmove_id UUID NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMEST"
        "AMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tcreated_by UUID, \n\tPRIMARY "
        "KEY (id), \n\tUNIQUE (move_id, code), \n\tFOREIGN KEY(move_id) REFERENCES mo"
        "ves (id)\n)\n\n"
    ),
    (
        "\nCREATE TABLE intents (\n\tcode VARCHAR(64) NOT NULL, \n\tname VARCHAR(255) "
        "NOT NULL, \n\tstep_id UUID NOT NULL, \n\tdescription TEXT, \n\tid UUID NOT NUL"
        "L, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tcreat"
        "ed_by UUID, \n\tPRIMARY KEY (id), \n\tUNIQUE (step_id, code), \n\tFOREIGN KEY("
        "step_id) REFERENCES steps (id)\n)\n\n"
    ),
    (
        "\nCREATE TABLE phrase_patterns (\n\tintent_id UUID NOT NULL, \n\tstatus VARCH"
        "AR(16) NOT NULL, \n\tcurrent_version_id UUID, \n\tupdated_at TIMESTAMP WITH "
        "TIME ZONE DEFAULT now() NOT NULL, \n\tid UUID NOT NULL, \n\tcreated_at TIMES"
        "TAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tcreated_by UUID, \n\tPRIMARY"
        " KEY (id), \n\tFOREIGN KEY(intent_id) REFERENCES intents (id)\n)\n\n"
    ),
    (
        "\nCREATE TABLE candidates (\n\tcanonical_frame TEXT NOT NULL, \n\tslots JSONB"
        " NOT NULL, \n\tintent_id UUID, \n\tconfidence FLOAT, \n\tepistemic_strength VA"
        "RCHAR(32), \n\tsource_sentence_ids UUID[] NOT NULL, \n\tcluster_key VARCHAR("
        "255), \n\tmatched_pattern_id UUID, \n\tstatus VARCHAR(16) NOT NULL, \n\t"
        "updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tid UUI"
        "D NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL"
        ", \n\tcreated_by UUID, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(intent_id) REFERE"
        "NCES intents (id), \n\tFOREIGN KEY(matched_pattern_id) REFERENCES phrase_p"
        "atterns (id)\n)\n\n"
    ),
    (
        "\nCREATE TABLE pattern_versions (\n\tpattern_id UUID NOT NULL, \n\tversion_no"
        " INTEGER NOT NULL, \n\tcanonical_frame TEXT NOT NULL, \n\tslots JSONB NOT NU"
        "LL, \n\tepistemic_strength VARCHAR(32) NOT NULL, \n\tclaim_type VARCHAR(64) "
        "NOT NULL, \n\tchange_note TEXT, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP"
        " WITH TIME ZONE DEFAULT now() NOT NULL, \n\tcreated_by UUID, \n\tPRIMARY KEY"
        " (id), \n\tUNIQUE (pattern_id, version_no), \n\tFOREIGN KEY(pattern_id) REFE"
        "RENCES phrase_patterns (id)\n)\n\n"
    ),
    (
        "\nCREATE TABLE phrase_variants (\n\tpattern_version_id UUID NOT NULL, \n\ttex"
        "t TEXT NOT NULL, \n\tregister VARCHAR(64), \n\tid UUID NOT NULL, \n\tcreated_a"
        "t TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tcreated_by UUID, \n\t"
        "PRIMARY KEY (id), \n\tFOREIGN KEY(pattern_version_id) REFERENCES pattern_v"
        "ersions (id)\n)\n\n"
    ),
    (
        "\nCREATE TABLE usage_constraints (\n\tpattern_version_id UUID NOT NULL, \n\te"
        "vidence_min VARCHAR(64), \n\tforbidden_contexts JSONB NOT NULL, \n\tallowed_"
        "sections JSONB NOT NULL, \n\tallowed_genres JSONB NOT NULL, \n\tid UUID NOT "
        "NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tcr"
        "eated_by UUID, \n\tPRIMARY KEY (id), \n\tUNIQUE (pattern_version_id), \n\tFORE"
        "IGN KEY(pattern_version_id) REFERENCES pattern_versions (id)\n)\n\n"
    ),
    (
        "\nCREATE TABLE evidence_provenances (\n\tpattern_version_id UUID NOT NULL, "
        "\n\tsource_type VARCHAR(16) NOT NULL, \n\tarticle_id UUID, \n\tsentence_ids UU"
        "ID[] NOT NULL, \n\tlicense_id UUID, \n\tid UUID NOT NULL, \n\tcreated_at TIMES"
        "TAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tcreated_by UUID, \n\tPRIMARY"
        " KEY (id), \n\tFOREIGN KEY(pattern_version_id) REFERENCES pattern_versions"
        " (id), \n\tFOREIGN KEY(article_id) REFERENCES articles (id), \n\tFOREIGN KEY"
        "(license_id) REFERENCES licenses (id)\n)\n\n"
    ),
    (
        "\nCREATE TABLE discipline_affinities (\n\tpattern_version_id UUID NOT NULL,"
        " \n\tdiscipline_code VARCHAR(128) NOT NULL, \n\tscore FLOAT NOT NULL, \n\tid U"
        "UID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NU"
        "LL, \n\tcreated_by UUID, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(pattern_version"
        "_id) REFERENCES pattern_versions (id)\n)\n\n"
    ),
    (
        "\nCREATE TABLE review_decisions (\n\tcandidate_id UUID, \n\tpattern_version_i"
        "d UUID, \n\tround SMALLINT NOT NULL, \n\tdecision VARCHAR(32) NOT NULL, \n\tre"
        "viewer_id UUID NOT NULL, \n\tcomment TEXT, \n\tid UUID NOT NULL, \n\tcreated_a"
        "t TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tcreated_by UUID, \n\t"
        "PRIMARY KEY (id), \n\tCONSTRAINT ck_review_decision_single_target CHECK (("
        "candidate_id IS NOT NULL AND pattern_version_id IS NULL) OR (candidate_i"
        "d IS NULL AND pattern_version_id IS NOT NULL)), \n\tCONSTRAINT ck_review_d"
        "ecision_round CHECK (round IN (1, 2)), \n\tFOREIGN KEY(candidate_id) REFER"
        "ENCES candidates (id), \n\tFOREIGN KEY(pattern_version_id) REFERENCES patt"
        "ern_versions (id), \n\tFOREIGN KEY(reviewer_id) REFERENCES api_clients (id"
        ")\n)\n\n"
    ),
    (
        "\nCREATE TABLE feedback (\n\tclient_id UUID NOT NULL, \n\trecommendation_id U"
        "UID NOT NULL, \n\tpattern_version_id UUID NOT NULL, \n\tsignal VARCHAR(16) N"
        "OT NULL, \n\tpayload JSONB, \n\tid UUID NOT NULL, \n\tcreated_at TIMESTAMP WIT"
        "H TIME ZONE DEFAULT now() NOT NULL, \n\tcreated_by UUID, \n\tPRIMARY KEY (id"
        "), \n\tFOREIGN KEY(client_id) REFERENCES api_clients (id), \n\tFOREIGN KEY(p"
        "attern_version_id) REFERENCES pattern_versions (id)\n)\n\n"
    ),
    ("ALTER TABLE moves ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    ("ALTER TABLE overrides ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    ("ALTER TABLE journal_profiles ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    ("ALTER TABLE journal_fingerprints ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    ("ALTER TABLE article_sections ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    ("ALTER TABLE audit_events ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    ("ALTER TABLE feedback ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    (
        "ALTER TABLE phrase_patterns ADD CONSTRAINT fk_pattern_current_version FO"
        "REIGN KEY(current_version_id) REFERENCES pattern_versions (id)"
    ),
    ("ALTER TABLE review_decisions ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    ("ALTER TABLE articles ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    ("ALTER TABLE candidates ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    ("ALTER TABLE phrase_patterns ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    ("ALTER TABLE api_clients ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    ("ALTER TABLE steps ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    ("ALTER TABLE taxonomy_releases ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    ("ALTER TABLE jobs ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    ("ALTER TABLE discipline_affinities ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    ("ALTER TABLE evidence_provenances ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    ("ALTER TABLE article_genres ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    ("ALTER TABLE sections ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    ("ALTER TABLE licenses ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    ("ALTER TABLE intents ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    ("ALTER TABLE usage_constraints ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    ("ALTER TABLE sentences ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    ("ALTER TABLE guideline_rules ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    ("ALTER TABLE pattern_versions ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    ("ALTER TABLE phrase_variants ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    ("ALTER TABLE recommendation_logs ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
    ("ALTER TABLE ref_enums ADD FOREIGN KEY(created_by) REFERENCES api_clients (id)"),
]
TABLES = [
    "audit_events",
    "licenses",
    "articles",
    "article_sections",
    "sentences",
    "api_clients",
    "journal_profiles",
    "guideline_rules",
    "journal_fingerprints",
    "candidates",
    "jobs",
    "phrase_patterns",
    "pattern_versions",
    "phrase_variants",
    "usage_constraints",
    "evidence_provenances",
    "discipline_affinities",
    "review_decisions",
    "feedback",
    "overrides",
    "recommendation_logs",
    "taxonomy_releases",
    "sections",
    "moves",
    "steps",
    "intents",
    "article_genres",
    "ref_enums",
]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    for statement in UPGRADE_SQL:
        op.execute(statement)


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
