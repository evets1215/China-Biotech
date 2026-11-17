import re
CN = re.compile(r"(china|chinese|shanghai|beijing|suzhou|jiangsu|hangzhou|zhejiang|nanjing|guangzhou|guangdong|shenzhen|chengdu|sichuan|wuhan|hubei|tianjin|shandong|qilu|hefei|anhui|chongqing|hunan|changsha|fujian|xiamen|hainan|jilin|shenyang|liaoning|dalian|hebei|shijiazhuang|henan|zhengzhou|xi'an|shaanxi|nanchang|jiangxi|kunming|yunnan|guangxi|harbin|zhuhai|wuxi|nantong|taizhou|lianyungang|changzhou|zhongshan|foshan|dongguan|ningbo|qingdao|jinan|yantai|hengrui|hansoh|innovent|beigene|junshi|akeso|cspc|chia tai|tianqing|sino |simcere|kelun|haihe|zai lab|hutchmed|hutchison|luye|fosun|henlius|alphamab|harbour biomed|innocare|ascentage|jacobio|allist|dizal|genor|cstone|i-mab|keymed|biokin|baili|duality|medilink|lepu|huadong|livzon|betta|kintor|gloria|transcenta|everest|antengene|abbisko|legend bio|gracell|carsgen|juventas|immunochina|bio-thera|mabwell|biotheus|leads bio|lanova|remegen|3sbio|sunshine guojian|zelgen|haisco|humanwell|jemincare|hinova|tyk medicines|avistone|inventisbio|inxmed|gensci|genfleet|d3 bio|adagene|elpiscience|laekna|ocumension|oricell|cellular biomedicine|jw therapeutics|hrain|unicar|yake|bioheng|nuwacell|suncadia|minghui|kangfang|zhongmei huadong)", re.I)

# Manual overrides (case-insensitive substring of the registered sponsor name). Classification is by the
# headquarters country of the sponsor's ultimate parent company. Curated by hand; see methods note.
CHINA_EXTRA = [
    "evopoint",
    "accendatech", "acerand", "adlai nortye", "arbele", "ascletis", "asieris", "askgene", "beone medicines", "casi pharma",
    "changchun", "chimagen", "conjupro", "curon bio", "fbd biologics", "fortvita", "forward pharmaceuticals",
    "full-life technologies", "gan and lee", "highfield bio", "huabo bio", "huahui health", "immvira", "impact therapeutics",
    "insilico medicine", "invox pharma", "kangabio", "kangpu bio", "keythera", "klus pharma", "lynk pharma", "lyvgen",
    "maxinovel", "multitude therapeutics", "newave pharma", "newsoara", "nucmito", "phrontline", "prg science",
    "regor pharma", "rinuagene", "salubris bio", "shengke pharma", "vibrant sciences", "velavigo", "westvac", "xynomic",
    "novarock", "sdk therapeutics", "new beta innovation", "new epsilon innovation", "racura oncology",
]
US_OVERRIDE = [  # would otherwise be caught by a China rule or default to Other
    "apollomics", "alloplex", "antiva bio", "avid radiopharm", "beyond air", "binacea", "boston immune", "bryet us",
    "dem biopharma", "grin therapeutics", "inimmune", "inmune bio", "larkspur", "lyndra", "mainline bio", "quadriga",
    "rs oncology", "sapu nano", "spectrum pharma", "stingray", "taiga bio", "tarus therapeutics", "telomir", "viracta",
    "xyone", "yourchoice", "xenthera", "salarius", "primevax", "geode therapeutics", "cornerstone pharma", "flame bio",
    "glycyx", "petra pharma", "mingsight", "genzada", "anwita", "eilean", "ocellaris", "recurv", "kymathera", "radalliance",
]
OTHER = [  # non-US, non-China parent, even though the trial has US sites
    "bergenbio", "artios", "peptomyc", "nelum", "oncopeptides", "novalgen", "immatics bio", "light chain bio", "txinno",
    "3b pharmaceuticals", "ab science", "abivax", "abl bio", "adc therapeutics", "adcendo", "affimed", "alentis", "amphista",
    "anaveon", "apollo therapeutics", "ariceum", "artios", "ascendis", "astellas", "astrazeneca", "medimmune", "alexion",
    "autolus", "avacta", "axcynsis", "basilea", "bavarian nordic", "bayer", "vividion", "bicycletx", "biofrontera", "bioinvent",
    "biontech", "blue earth", "boehringer", "boryung", "brenus", "carrick", "cdr-life", "cellectis", "celyad", "centessa",
    "chong kun dang", "chordia", "chugai", "cj bioscience", "clarity pharma", "compugen", "cosmo tech", "crescendo bio",
    "crispr therapeutics", "daiichi", "debiopharm", "domain therapeutics", "duke street", "eisbach", "ellipses", "emd serono",
    "merck healthcare kgaa", "engene", "engeneic", "enterome", "essa pharma", "eutilex", "excellthera", "exscientia",
    "famewave", "feldan", "forx", "fusion pharma", "futurechem", "gadeta", "gamida", "gammadelta", "genentech",
    "hoffmann-la roche", "genmab", "genome & company", "gi innovation", "glaxosmithkline", "glenmark", "ichnos", "hanmi",
    "heidelberg pharma", "hemerion", "heparegenix", "iksuda", "imcheck", "immuneoncia", "immunocore", "imugene",
    "impact biotech", "innate pharma", "ipsen", "iox therapeutics", "j ints bio", "jubilant", "kahr", "kyowa kirin",
    "lakefront", "lava therapeutics", "lg chem", "ligachem", "lutris", "medac", "medicenna", "mediwound", "merus",
    "molecular partners", "myricx", "nbe-therapeutics", "nectin therapeutics", "nerviano", "nihon medi", "novartis",
    "novo nordisk", "dicerna", "numab", "obi pharma", "oncomatryx", "oncorena", "ono pharma", "orano med", "orion corp",
    "orum therapeutics", "ottimo", "peptidream", "pharmamar", "pierre fabre", "precirix", "prestige bio", "prokarium",
    "proteinqure", "pure biologics", "qurient", "radiopharm theranostics", "repare", "rovi pharma", "sairopa",
    "samsung bioepis", "sandoz", "sanofi", "selecxine", "servier", "shionogi", "silence therapeutics", "sillajen",
    "sk life science", "smart immune", "sotio", "st pharm", "stcube", "step pharma", "storm therapeutics", "sumitomo",
    "sun pharma", "symphogen", "t.o.a.d.", "tagworks", "taiho", "takeda", "tanabe", "tessa therapeutics", "tetragon",
    "teva", "theratechnologies", "theravectys", "tiumbio", "tolremo", "trogenix", "tyrnovo", "ucb biopharma",
    "united immunity", "valerio", "virogin", "xspray", "yuhan", "zymeworks", "zumutor", "asahi kasei", "eisai", "astex",
    "hummingbird", "chimeric therapeutics", "alpha-9", "aurinia", "acepodia", "1st biotherapeutics", "bold therapeutics",
    "bright peak", "glyconex", "calgent", "synermore", "lin bioscience", "otsuka", "institut de recherches",
    "symbio pharma", "lion tcr", "henlix",
]


def sponsor_country(name: str, site_countries) -> str:
    """Return 'China', 'US' or 'Other' for an industry sponsor."""
    n = (name or "").lower()
    sites = set(site_countries or [])
    if any(k in n for k in US_OVERRIDE):
        return "US"
    if any(k in n for k in CHINA_EXTRA) or CN.search(n):
        return "China"
    if any(k in n for k in OTHER):
        return "Other"
    if sites and sites <= {"China"}:
        return "China"
    if "United States" in sites:
        return "US"
    return "Other"
