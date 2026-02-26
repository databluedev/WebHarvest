"""Pydantic schemas for Google Data APIs (Scrapper Pool)."""

from pydantic import BaseModel, Field


# --- Request ---

class GoogleSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2048, description="Search query")
    num_results: int = Field(10, ge=1, le=100, description="Number of results (max 100)")
    page: int = Field(1, ge=1, le=10, description="Result page (1-10)")
    language: str = Field("en", description="Language code (hl parameter)")
    country: str | None = Field(None, description="Country code for geo-targeting (gl parameter, e.g. us, uk, in)")
    safe_search: bool = Field(False, description="Enable safe search filter")
    time_range: str | None = Field(
        None,
        pattern=r"^(hour|day|week|month|year)$",
        description="Time filter: hour, day, week, month, year",
    )


# --- Response models ---

class Sitelink(BaseModel):
    title: str
    url: str


class GoogleOrganicResult(BaseModel):
    model_config = {"exclude_none": True}

    position: int = Field(..., description="1-indexed rank on the page")
    title: str
    url: str
    displayed_url: str | None = None
    snippet: str | None = None
    date: str | None = Field(None, description="Published date if shown")
    sitelinks: list[Sitelink] | None = None


class FeaturedSnippet(BaseModel):
    model_config = {"exclude_none": True}

    title: str
    url: str
    content: str
    type: str = Field("paragraph", description="paragraph, list, or table")


class PeopleAlsoAsk(BaseModel):
    question: str
    snippet: str | None = None


class RelatedSearch(BaseModel):
    query: str


class KnowledgePanel(BaseModel):
    model_config = {"exclude_none": True}

    title: str
    type: str | None = None
    description: str | None = None
    source: str | None = None
    image_url: str | None = None
    attributes: dict[str, str] | None = None


class GoogleSearchResponse(BaseModel):
    model_config = {"exclude_none": True}

    success: bool = True
    query: str
    total_results: str | None = Field(None, description="e.g. 'About 1,230,000 results'")
    time_taken: float = Field(..., description="API response time in seconds")
    organic_results: list[GoogleOrganicResult] = []
    featured_snippet: FeaturedSnippet | None = None
    people_also_ask: list[PeopleAlsoAsk] = []
    related_searches: list[RelatedSearch] = []
    knowledge_panel: KnowledgePanel | None = None


# ═══════════════════════════════════════════════════════════════════
# Google Shopping
# ═══════════════════════════════════════════════════════════════════


class GoogleShoppingRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2048, description="Product search query")
    num_results: int = Field(10, ge=1, le=100, description="Number of products (max 100)")
    page: int = Field(1, ge=1, le=10, description="Starting page (1-10)")
    language: str = Field("en", description="Language code (hl parameter)")
    country: str | None = Field(None, description="Country code for geo-targeting (gl parameter)")

    # Filters
    sort_by: str | None = Field(
        None,
        pattern=r"^(relevance|price_low|price_high|rating|reviews)$",
        description="Sort order: relevance, price_low, price_high, rating, reviews",
    )
    min_rating: int | None = Field(
        None, ge=1, le=4, description="Minimum star rating (1-4)"
    )


class GoogleShoppingProduct(BaseModel):
    model_config = {"exclude_none": True}

    position: int = Field(..., description="1-indexed rank")
    title: str
    url: str
    image_url: str | None = None
    price: str | None = Field(None, description="Displayed price string (e.g. '$29.99')")
    price_value: float | None = Field(None, description="Parsed numeric price")
    currency: str | None = Field(None, description="Currency code (USD, EUR, etc.)")
    original_price: str | None = Field(None, description="Original price if on sale")
    merchant: str | None = Field(None, description="Store/seller name")
    rating: float | None = Field(None, description="Star rating (0-5)")
    review_count: int | None = Field(None, description="Number of reviews")
    shipping: str | None = Field(None, description="Shipping info (e.g. 'Free shipping')")
    badge: str | None = Field(None, description="Special badge (Best seller, Great price, etc.)")


class GoogleShoppingResponse(BaseModel):
    model_config = {"exclude_none": True}

    success: bool = True
    query: str
    total_results: str | None = None
    time_taken: float = Field(..., description="API response time in seconds")
    filters_applied: dict[str, str | float | bool] | None = Field(
        None, description="Echo of active filters"
    )
    products: list[GoogleShoppingProduct] = []
    related_searches: list[RelatedSearch] = []


# ═══════════════════════════════════════════════════════════════════
# Google Maps
# ═══════════════════════════════════════════════════════════════════


class GoogleMapsRequest(BaseModel):
    # --- Search mode ---
    query: str | None = Field(
        None, max_length=2048,
        description="Search query (e.g. 'restaurants near Times Square')",
    )
    coordinates: str | None = Field(
        None,
        pattern=r"^-?\d+\.?\d*,-?\d+\.?\d*$",
        description="GPS coordinates as 'lat,lng' (e.g. '40.7580,-73.9855')",
    )
    radius: int | None = Field(
        None, ge=100, le=50000,
        description="Search radius in meters (default 5000, max 50000)",
    )
    zoom: int | None = Field(
        None, ge=1, le=21,
        description="Map zoom level (1-21, auto-calculated from radius if not set)",
    )

    # --- Filtering ---
    type: str | None = Field(
        None,
        description=(
            "Place type filter (e.g. restaurant, hotel, gas_station, hospital, "
            "cafe, bar, gym, pharmacy, bank, supermarket, park, museum, airport)"
        ),
    )
    keyword: str | None = Field(
        None, max_length=500,
        description="Additional keyword to filter results (e.g. 'vegetarian', 'rooftop')",
    )
    min_rating: float | None = Field(
        None, ge=1.0, le=5.0,
        description="Minimum star rating filter (1.0-5.0)",
    )
    open_now: bool = Field(False, description="Only show places that are currently open")
    price_level: int | None = Field(
        None, ge=1, le=4,
        description="Price range filter: 1=$, 2=$$, 3=$$$, 4=$$$$",
    )
    sort_by: str | None = Field(
        None,
        pattern=r"^(relevance|distance|rating|reviews)$",
        description="Sort order: relevance, distance, rating, reviews",
    )

    # --- Pagination ---
    num_results: int = Field(20, ge=1, le=200, description="Number of places (max 200)")

    # --- Detail mode (single place lookup) ---
    place_id: str | None = Field(
        None,
        description="Google Place ID for detailed lookup (e.g. 'ChIJN1t_tDeuEmsRUsoyG')",
    )
    cid: str | None = Field(
        None,
        description="CID / Ludocid — permanent business identifier",
    )
    data: str | None = Field(
        None,
        description="Google Maps data parameter (encoded place reference)",
    )

    # --- Data options ---
    language: str = Field("en", description="Language code (hl parameter)")
    country: str | None = Field(
        None, description="Country code for geo-targeting (gl parameter)",
    )
    include_reviews: bool = Field(False, description="Include reviews for each place")
    reviews_limit: int = Field(
        5, ge=1, le=20,
        description="Maximum reviews per place (1-20, requires include_reviews=true)",
    )
    reviews_sort: str = Field(
        "most_relevant",
        pattern=r"^(most_relevant|newest|highest|lowest)$",
        description="Review sort order: most_relevant, newest, highest, lowest",
    )


class GoogleMapsReview(BaseModel):
    model_config = {"exclude_none": True}

    author_name: str
    author_url: str | None = None
    profile_photo_url: str | None = None
    rating: float | None = Field(None, description="Star rating (1-5)")
    text: str | None = None
    relative_time: str | None = Field(None, description="e.g. '2 months ago'")
    language: str | None = None


class GoogleMapsPlace(BaseModel):
    model_config = {"exclude_none": True}

    # Identity
    position: int = Field(..., description="1-indexed rank in results")
    title: str = Field(..., description="Business/place name")
    place_id: str | None = Field(None, description="Google Place ID (ChIJ...)")
    cid: str | None = Field(None, description="CID / Ludocid (hex, e.g. 0x...:0x...)")
    data_id: str | None = Field(
        None, description="Hex CID pair (e.g. '0x3bb6e59021aaaaab:0xfbacafc56bc15ed7')",
    )
    data_cid: str | None = Field(
        None, description="Decimal CID (e.g. '18132222127050743511')",
    )
    provider_id: str | None = Field(
        None, description="Google provider ID (e.g. '/g/11f57yyvm7')",
    )

    # Location
    address: str | None = None
    gps_coordinates: dict[str, float] | None = Field(
        None, description="GPS coordinates {latitude, longitude}",
    )
    latitude: float | None = None
    longitude: float | None = None
    plus_code: str | None = Field(None, description="Google Plus Code")

    # Links
    url: str = Field(..., description="Google Maps URL")
    google_maps_url: str | None = Field(
        None, description="Direct Google Maps link for this place",
    )
    website: str | None = None
    menu_url: str | None = None
    order_url: str | None = Field(None, description="Online ordering link")
    reservation_url: str | None = Field(None, description="Booking/reservation link")

    # Contact
    phone: str | None = None
    international_phone: str | None = None

    # Ratings
    rating: float | None = Field(None, description="Star rating (0-5)")
    reviews: int | None = Field(None, description="Number of reviews")
    review_count: int | None = Field(None, description="Number of reviews (alias)")
    price: str | None = Field(None, description="Price display (e.g. '$', '$$', '$10-20')")
    price_level: int | None = Field(None, description="1-4 ($ to $$$$)")
    price_level_text: str | None = Field(None, description="'$' to '$$$$'")

    # Status
    business_status: str | None = Field(
        None, description="OPERATIONAL, CLOSED_TEMPORARILY, CLOSED_PERMANENTLY",
    )
    open_state: str | None = Field(
        None, description="Current status text (e.g. 'Open', 'Closed ⋅ Opens 7 AM')",
    )
    open_now: bool | None = None

    # Categories
    type: str | None = Field(None, description="Primary type (e.g. 'Restaurant')")
    type_id: str | None = Field(
        None, description="Machine-readable primary type (e.g. 'restaurant')",
    )
    subtypes: list[str] | None = Field(
        None, description="All categories (e.g. ['Italian restaurant', 'Pizza'])",
    )
    type_ids: list[str] | None = Field(
        None,
        description="Machine-readable type IDs (e.g. ['italian_restaurant', 'pizza'])",
    )

    # Media
    thumbnail: str | None = Field(None, description="Thumbnail photo URL")
    image: str | None = Field(None, description="Full-size main image URL")
    photos: list[str] | None = Field(None, description="Photo URLs")
    photo_count: int | None = None

    # Hours
    hours: str | None = Field(None, description="Hours summary (e.g. 'Opens at 9 AM')")
    working_hours: list[dict[str, str]] | None = Field(
        None,
        description="Full business hours [{day: 'Monday', hours: '9 AM – 10 PM'}, ...]",
    )

    # Reviews
    user_reviews: list[GoogleMapsReview] | None = None

    # Extras
    description: str | None = None
    extensions: list[dict[str, list[str]]] | None = Field(
        None,
        description="Grouped attributes (e.g. [{service_options: ['Dine-in', 'Delivery']}, ...])",
    )
    attributes: list[str] | None = Field(
        None,
        description="Flat service attributes (e.g. ['Wheelchair accessible', 'Outdoor seating'])",
    )
    popular_times: dict[str, list[dict[str, int]]] | None = Field(
        None,
        description="Popular times by day {Monday: [{hour: 9, percent: 30}, ...]}",
    )


class GoogleMapsResponse(BaseModel):
    model_config = {"exclude_none": True}

    success: bool = True
    query: str | None = None
    coordinates_used: str | None = Field(
        None, description="GPS coordinates used for the search",
    )
    search_type: str = Field(
        "search", description="search, place_details, or nearby",
    )
    total_results: str | None = None
    time_taken: float = Field(..., description="API response time in seconds")
    filters_applied: dict[str, str | float | bool] | None = None
    places: list[GoogleMapsPlace] = []
    related_searches: list[RelatedSearch] = []


# ===================================================================
# Google News
# ===================================================================


class GoogleNewsRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2048, description="News search query")
    num_results: int = Field(100, ge=1, le=500, description="Number of articles (max 500)")
    language: str = Field("en", description="Language code (hl parameter)")
    country: str | None = Field(
        None, description="Country code for geo-targeting (gl parameter, e.g. us, uk, in)"
    )
    time_range: str | None = Field(
        None,
        pattern=r"^(hour|day|week|month|year)$",
        description="Time filter: hour, day, week, month, year",
    )
    sort_by: str | None = Field(
        None,
        pattern=r"^(relevance|date)$",
        description="Sort order: relevance, date",
    )


class GoogleNewsArticle(BaseModel):
    model_config = {"exclude_none": True}

    position: int = Field(..., description="1-indexed rank in results")
    title: str
    url: str
    source: str | None = Field(None, description="News outlet name")
    source_url: str | None = Field(None, description="News outlet URL/domain")
    date: str | None = Field(None, description="Display date (e.g. '2 hours ago')")
    published_date: str | None = Field(None, description="ISO date if available")
    snippet: str | None = None
    thumbnail: str | None = Field(None, description="Image URL")


class GoogleNewsResponse(BaseModel):
    model_config = {"exclude_none": True}

    success: bool = True
    query: str
    total_results: str | None = None
    time_taken: float = Field(..., description="API response time in seconds")
    source_strategy: str = Field(
        ..., description="Strategies that produced results (combined with '+'): searxng_google_news, searxng_all_news, rss, nodriver"
    )
    articles: list[GoogleNewsArticle] = []
    related_searches: list[RelatedSearch] = []


# ===================================================================
# Google Jobs (Careers) — reverse-engineered AF_initDataCallback
# ===================================================================


class GoogleJobsRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2048, description="Job search query")
    num_results: int = Field(20, ge=1, le=500, description="Number of jobs (max 500, 20 per page)")
    page: int = Field(1, ge=1, le=100, description="Page number (1-indexed)")
    has_remote: bool | None = Field(None, description="Filter remote-eligible jobs only")
    target_level: list[str] | None = Field(
        None,
        description="Experience levels: INTERN_AND_APPRENTICE, EARLY, MID, ADVANCED, DIRECTOR",
    )
    employment_type: list[str] | None = Field(
        None,
        description="Job types: FULL_TIME, PART_TIME, TEMPORARY, INTERN",
    )
    company: list[str] | None = Field(
        None,
        description="Organizations: Google, DeepMind, GFiber, Waymo, Wing, YouTube, Verily Life Sciences",
    )
    location: list[str] | None = Field(
        None, description="Location filters (e.g. 'New York, NY, USA')"
    )
    degree: str | None = Field(
        None,
        description="Degree filter: PURSUING_DEGREE, ASSOCIATE, BACHELORS, MASTERS, PHD",
    )
    skills: str | None = Field(None, description="Skills filter (e.g. 'coding')")
    sort_by: str = Field("relevance", description="Sort order: relevance, date")


class GoogleJobLocation(BaseModel):
    model_config = {"exclude_none": True}

    display_name: str = Field(..., description="Full location string (e.g. 'Kirkland, WA, USA')")
    city: str | None = Field(None, description="City name")
    state: str | None = Field(None, description="State/region code")
    country: str | None = Field(None, description="Country code (e.g. US, PL, SG)")
    postal_code: str | None = None


class GoogleJobListing(BaseModel):
    model_config = {"exclude_none": True}

    position: int = Field(..., description="1-indexed rank in results")
    job_id: str = Field(..., description="Numeric job ID")
    title: str
    company: str = Field(..., description="Organization name (Google, DeepMind, etc.)")
    locations: list[GoogleJobLocation] = []
    apply_url: str | None = Field(None, description="Direct apply/sign-in URL")
    detail_url: str | None = Field(None, description="Job detail page URL")
    description_html: str | None = Field(None, description="Job description as HTML")
    responsibilities_html: str | None = Field(None, description="Responsibilities as HTML")
    qualifications_html: str | None = Field(None, description="Combined qualifications as HTML")
    min_qualifications_html: str | None = Field(None, description="Minimum qualifications only as HTML")
    benefits_html: str | None = Field(None, description="Benefits/compensation as HTML")
    experience_level: str | None = Field(None, description="Entry, Mid, Advanced, or Director")
    category_ids: list[int] | None = Field(None, description="Category codes (2=SWE, 3=TechInfra, etc.)")
    created_at: str | None = Field(None, description="ISO date when job was first posted")
    updated_at: str | None = Field(None, description="ISO date when job was last updated")


class GoogleJobsResponse(BaseModel):
    model_config = {"exclude_none": True}

    success: bool = True
    query: str
    total_results: int | None = Field(None, description="Total jobs matching query across all pages")
    page: int = Field(1, description="Current page number")
    page_size: int = Field(20, description="Jobs per page")
    time_taken: float = Field(..., description="API response time in seconds")
    jobs: list[GoogleJobListing] = []
    companies: list[str] | None = Field(None, description="Available company/org names from ds:0")
