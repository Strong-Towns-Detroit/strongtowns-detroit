from bza_site_matching import address_candidates, clean_street


def test_multi_address_single_street():
    assert address_candidates(
        "5604, 5610 & 5614 Florida Between McGraw and Wagner"
    ) == [(5604, "FLORIDA"), (5610, "FLORIDA"), (5614, "FLORIDA")]


def test_multiple_street_groups():
    assert address_candidates(
        "299, 303 & 325 Smith and 7719 Brush, between Brush and John R"
    ) == [
        (299, "SMITH"), (303, "SMITH"), (325, "SMITH"), (7719, "BRUSH")
    ]


def test_aka_address_is_retained():
    assert address_candidates("7250 Mack (aka 7200 Mack) Between Field and East Grand") == [
        (7250, "MACK"), (7200, "MACK")
    ]


def test_street_normalization():
    assert clean_street("W. Eight Mile Rd.") == "W EIGHT MILE"
    assert clean_street("W. 8 Mile Road") == "W EIGHT MILE"
    assert clean_street("Martin Luther King Jr. Blvd.") == "MARTIN LUTHER KING"
    assert clean_street("Leicester Court") == "LEICESTER"
    assert clean_street("West Eight Mile Rd.") == "W EIGHT MILE"
    assert clean_street("Mount Elliott") == "MT ELLIOTT"
    assert clean_street("Fourth Street") == "4TH"
    assert clean_street("St. Anne") == "ST ANNE"
    assert clean_street("Southfield Fwy. Freeway") == "SOUTHFIELD"


def test_ampersand_between_distinct_streets():
    assert address_candidates("17405 Lahser & 17371 Redford between Redford and Willmarth") == [
        (17405, "LAHSER"), (17371, "REDFORD")
    ]


def test_thru_range_keeps_both_endpoints():
    assert address_candidates("10 thru 36 W McNichols between Woodward and John R") == [
        (10, "W MCNICHOLS"), (36, "W MCNICHOLS")
    ]


def test_abbreviated_range_expands_endpoint():
    assert address_candidates("5630-36 Plumer, between Junction and McKinstry") == [
        (5630, "PLUMER"), (5636, "PLUMER")
    ]


def test_unparenthesized_aka_keeps_both_addresses():
    assert address_candidates(
        "8005 aka 8009 E. Jefferson, between Van Dyke and Parker"
    ) == [(8009, "E JEFFERSON"), (8005, "E JEFFERSON")]


def test_missing_space_after_house_number():
    assert address_candidates(
        "2639 and 2647Austin Street between St. Anne and 18th St."
    ) == [(2639, "AUSTIN"), (2647, "AUSTIN")]


def test_corner_phrase_is_not_part_of_street():
    assert address_candidates(
        "1728 Michigan Ave, Corner of Cochrane and Harrison"
    ) == [(1728, "MICHIGAN")]


def test_and_list_before_final_number_keeps_all_addresses():
    assert address_candidates(
        "4213, 4219 and 4225 Fourth Street between Willis and Calumet"
    ) == [(4213, "4TH"), (4219, "4TH"), (4225, "4TH")]


def test_comma_ampersand_list_keeps_all_addresses():
    assert address_candidates(
        "501, 511, & 519 E. Bethune, between John R and Brush"
    ) == [(501, "E BETHUNE"), (511, "E BETHUNE"), (519, "E BETHUNE")]


def test_parenthetical_secondary_address_is_retained():
    assert address_candidates(
        "2733 Harrison (2741 Harrison) between Pine and Spruce"
    ) == [(2733, "HARRISON"), (2741, "HARRISON")]
