"""Independent published BIP-93 vectors for the Codex32 implementation."""

from itertools import combinations

import pytest

from seedsigner.models import codex32 as codex32_model
from seedsigner.models import codex32_min
from seedsigner.models.codex32_min import Codex32String, CodexError


def test_bip93_vector_1_unshared_secret():
    secret = Codex32String("ms10testsxxxxxxxxxxxxxxxxxxxxxxxxxx4nzvca9cmczlw")

    assert secret.share_idx == "s"
    assert secret.data == bytes.fromhex("318c6318c6318c6318c6318c6318c631")


def test_bip93_vector_2_recovery_and_derivation():
    share_a = Codex32String("MS12NAMEA320ZYXWVUTSRQPNMLKJHGFEDCAXRPP870HKKQRM")
    share_c = Codex32String("MS12NAMECACDEFGHJKLMNPQRSTUVWXYZ023FTR2GDZMPY6PN")
    expected_d = "MS12NAMEDLL4F8JLH4E5VDVULDLFXU2JHDNLSM97XVENRXEG"
    expected_s = "MS12NAMES6XQGUZTTXKEQNJSJZV4JV3NZ5K3KWGSPHUH6EVW"

    recovered_s = Codex32String.interpolate_at([share_a, share_c], target="s")
    derived_d = Codex32String.interpolate_at([share_a, share_c], target="d")

    assert recovered_s.s == expected_s
    assert recovered_s.data == bytes.fromhex("d1808e096b35b209ca12132b264662a5")
    assert derived_d.s == expected_d


def test_bip93_vector_3_every_threshold_combination_recovers_secret():
    share_strings = {
        "a": "ms13casha320zyxwvutsrqpnmlkjhgfedca2a8d0zehn8a0t",
        "c": "ms13cashcacdefghjklmnpqrstuvwxyz023949xq35my48dr",
        "d": "ms13cashd0wsedstcdcts64cd7wvy4m90lm28w4ffupqs7rm",
        "e": "ms13casheekgpemxzshcrmqhaydlp6yhms3ws7320xyxsar9",
        "f": "ms13cashf8jh6sdrkpyrsp5ut94pj8ktehhw2hfvyrj48704",
    }
    expected_s = "ms13cashsllhdmn9m42vcsamx24zrxgs3qqjzqud4m0d6nln"
    shares = [Codex32String(value) for value in share_strings.values()]

    for share_subset in combinations(shares, 3):
        recovered = Codex32String.interpolate_at(list(share_subset), target="s")
        assert recovered.s == expected_s
        assert recovered.data == bytes.fromhex("ffeeddccbbaa99887766554433221100")


BIP93_VECTOR_4_SECRETS = [
    "ms10leetsllhdmn9m42vcsamx24zrxgs3qrl7ahwvhw4fnzrhve25gvezzyqqtum9pgv99ycma",
    "ms10leetsllhdmn9m42vcsamx24zrxgs3qrl7ahwvhw4fnzrhve25gvezzyqpj82dp34u6lqtd",
    "ms10leetsllhdmn9m42vcsamx24zrxgs3qrl7ahwvhw4fnzrhve25gvezzyqzsrs4pnh7jmpj5",
    "ms10leetsllhdmn9m42vcsamx24zrxgs3qrl7ahwvhw4fnzrhve25gvezzyqrfcpap2w8dqezy",
    "ms10leetsllhdmn9m42vcsamx24zrxgs3qrl7ahwvhw4fnzrhve25gvezzyqy5tdvphn6znrf0",
    "ms10leetsllhdmn9m42vcsamx24zrxgs3qrl7ahwvhw4fnzrhve25gvezzyq9dsuypw2ragmel",
    "ms10leetsllhdmn9m42vcsamx24zrxgs3qrl7ahwvhw4fnzrhve25gvezzyqx05xupvgp4v6qx",
    "ms10leetsllhdmn9m42vcsamx24zrxgs3qrl7ahwvhw4fnzrhve25gvezzyq8k0h5p43c2hzsk",
    "ms10leetsllhdmn9m42vcsamx24zrxgs3qrl7ahwvhw4fnzrhve25gvezzyqgum7hplmjtr8ks",
    "ms10leetsllhdmn9m42vcsamx24zrxgs3qrl7ahwvhw4fnzrhve25gvezzyqf9q0lpxzt5clxq",
    "ms10leetsllhdmn9m42vcsamx24zrxgs3qrl7ahwvhw4fnzrhve25gvezzyq28y48pyqfuu7le",
    "ms10leetsllhdmn9m42vcsamx24zrxgs3qrl7ahwvhw4fnzrhve25gvezzyqt7ly0paesr8x0f",
    "ms10leetsllhdmn9m42vcsamx24zrxgs3qrl7ahwvhw4fnzrhve25gvezzyqvrvg7pqydv5uyz",
    "ms10leetsllhdmn9m42vcsamx24zrxgs3qrl7ahwvhw4fnzrhve25gvezzyqd6hekpea5n0y5j",
    "ms10leetsllhdmn9m42vcsamx24zrxgs3qrl7ahwvhw4fnzrhve25gvezzyqwcnrwpmlkmt9dt",
    "ms10leetsllhdmn9m42vcsamx24zrxgs3qrl7ahwvhw4fnzrhve25gvezzyq0pgjxpzx0ysaam",
]


@pytest.mark.parametrize("secret_value", BIP93_VECTOR_4_SECRETS)
def test_bip93_vector_4_padding_variants(secret_value):
    secret = Codex32String(secret_value)
    assert secret.data == bytes.fromhex(
        "ffeeddccbbaa99887766554433221100ffeeddccbbaa99887766554433221100"
    )

    with pytest.raises(codex32_model.Codex32InputError, match="Expected 48"):
        codex32_model.validate_codex32_s_share(secret_value)


def test_bip93_vector_5_long_secret():
    secret = Codex32String(
        "MS100C8VSM32ZXFGUHPCHTLUPZRY9X8GF2TVDW0S3JN54KHCE6MUA7LQPZYGSFJD6AN074RXV"
        "CEMLH8WU3TK925ACDEFGHJKLMNPQRSTUVWXY06FHPV80UNDVARHRAK"
    )
    assert secret.data == bytes.fromhex(
        "dc5423251cb87175ff8110c8531d0952d8d73e1194e95b5f19d6f9df7c011111"
        "04c9baecdfea8cccc677fb9ddc8aec5553b86e528bcadfdcc201c17c638c47e9"
    )


BIP93_INVALID_VECTORS = [
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxve740yyge2ghq",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxve740yyge2ghp",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxlk3yepcstwr",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxx6pgnv7jnpcsp",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxx0cpvr7n4geq",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxm5252y7d3lr",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxrd9sukzl05ej",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxc55srw5jrm0",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxgc7rwhtudwc",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxx4gy22afwghvs",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxe8yfm0",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxvm597d",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxme084q0vpht7pe0",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxme084q0vpht7pew",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxqyadsp3nywm8a",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxzvg7ar4hgaejk",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxcznau0advgxqe",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxch3jrc6j5040j",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx52gxl6ppv40mcv",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx7g4g2nhhle8fk",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx63m45uj8ss4x8",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxy4r708q7kg65x",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxurfvwmdcmymdufv",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxcsyppjkd8lz4hx3",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxu6hwvl5p0l9xf3c",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxwqey9rfs6smenxa",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxv70wkzrjr4ntqet",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx3hmlrmpa4zl0v",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxrfggf88znkaup",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxpt7l4aycv9qzj",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxus27z9xtyxyw3",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxcwm4re8fs78vn",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxw0a4c70rfefn4",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxk4pavy5n46nea",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxx9lrwar5zwng4w",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxr335l5tv88js3",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxvu7q9nz8p7dj68v",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxpq6k542scdxndq3",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxkmfw6jm270mz6ej",
    "ms12fauxxxxxxxxxxxxxxxxxxxxxxxxxxzhddxw99w7xws",
    "ms12fauxxxxxxxxxxxxxxxxxxxxxxxxxxxx42cux6um92rz",
    "ms12fauxxxxxxxxxxxxxxxxxxxxxxxxxxxxxarja5kqukdhy9",
    "ms12fauxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxky0ua3ha84qk8",
    "ms12fauxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx9eheesxadh2n2n9",
    "ms12fauxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx9llwmgesfulcj2z",
    "ms12fauxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx02ev7caq6n9fgkf",
    "ms10fauxxxxxxxxxxxxxxxxxxxxxxxxxxxx0z26tfn0ulw3p",
    "ms1fauxxxxxxxxxxxxxxxxxxxxxxxxxxxxxda3kr3s0s2swg",
    "0fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxuqxkk05lyf3x2",
    "10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxuqxkk05lyf3x2",
    "ms0fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxuqxkk05lyf3x2",
    "m10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxuqxkk05lyf3x2",
    "s10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxuqxkk05lyf3x2",
    "0fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxhkd4f70m8lgws",
    "10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxhkd4f70m8lgws",
    "m10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxx8t28z74x8hs4l",
    "s10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxh9d0fhnvfyx3x",
    "Ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxuqxkk05lyf3x2",
    "mS10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxuqxkk05lyf3x2",
    "MS10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxuqxkk05lyf3x2",
    "ms10FAUXsxxxxxxxxxxxxxxxxxxxxxxxxxxuqxkk05lyf3x2",
    "ms10fauxSxxxxxxxxxxxxxxxxxxxxxxxxxxuqxkk05lyf3x2",
    "ms10fauxsXXXXXXXXXXXXXXXXXXXXXXXXXXuqxkk05lyf3x2",
    "ms10fauxsxxxxxxxxxxxxxxxxxxxxxxxxxxUQXKK05LYF3X2",
]


@pytest.mark.parametrize("invalid_value", BIP93_INVALID_VECTORS)
def test_bip93_published_invalid_vectors(invalid_value):
    with pytest.raises(CodexError):
        Codex32String(invalid_value)


def test_recovery_rejects_wrong_count_and_mixed_headers():
    share_a = Codex32String("MS12NAMEA320ZYXWVUTSRQPNMLKJHGFEDCAXRPP870HKKQRM")
    share_c = Codex32String("MS12NAMECACDEFGHJKLMNPQRSTUVWXYZ023FTR2GDZMPY6PN")
    other_set = Codex32String("ms13cashcacdefghjklmnpqrstuvwxyz023949xq35my48dr")

    with pytest.raises(codex32_model.Codex32InputError, match="exactly 2"):
        codex32_model.recover_secret_share([share_a])

    with pytest.raises(codex32_model.Codex32InputError, match="matching"):
        codex32_model.recover_secret_share([share_a, other_set])

    assert codex32_model.recover_secret_share([share_a, share_c]).share_idx == "s"


def test_product_profile_rejects_threshold_above_five_on_first_share():
    share = Codex32String("ms13casha320zyxwvutsrqpnmlkjhgfedca2a8d0zehn8a0t")
    values = share.data_part_values
    values[0] = codex32_min.CHARSET_MAP["6"]
    unsupported = codex32_min.ms32_encode(values)

    with pytest.raises(codex32_model.Codex32InputError, match="above 5"):
        codex32_model.Codex32ShareCollection.from_first_share(
            codex32_model.parse_codex32_share(unsupported)
        )


def test_entering_s_mid_collection_completes_recovery_immediately():
    share_a = "MS12NAMEA320ZYXWVUTSRQPNMLKJHGFEDCAXRPP870HKKQRM"
    secret_s = "MS12NAMES6XQGUZTTXKEQNJSJZV4JV3NZ5K3KWGSPHUH6EVW"
    collection = codex32_model.Codex32ShareCollection.from_first_share(
        codex32_model.parse_codex32_share(share_a)
    )

    collection.add_share(codex32_model.parse_codex32_share(secret_s))

    assert collection.ready is True
    assert collection.recovered_secret_share().s == secret_s
