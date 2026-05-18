from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app


def book(
    title: str,
    author: str = "",
    genre: str = "",
    fmt: str = "paperback",
    confidence: float = 0.82,
    notes: str = "Extracted from staged May 17 photo intake.",
) -> dict[str, Any]:
    return {
        "title": title,
        "author": author,
        "isbn": "",
        "publisher": "",
        "published_year": "",
        "genre": genre,
        "format": fmt,
        "condition": "",
        "confidence": confidence,
        "notes": notes,
    }


def registration(status: str, charter: str, **extra: Any) -> dict[str, Any]:
    payload = {
        "status": status,
        "charter_number": charter,
        "checked_at": "2026-05-18T04:30:00+00:00",
    }
    payload.update(extra)
    return payload


LIBRARIES: list[dict[str, Any]] = [
    {
        "library_name": "Red Blue Driveway Little Free Library",
        "library_description": (
            "Red-front, blue-sided Little Free Library by a driveway under a large tree. "
            "Staged from May 17, 2026 book and surroundings photos."
        ),
        "charter_number": "77609",
        "charter_registration": registration("not_found", "77609"),
        "geolocation": {
            "latitude": 39.41923611111111,
            "longitude": -77.42944444444444,
            "source": "photo_exif",
            "confidence": 0.99,
        },
        "place_clues": ["driveway", "large tree", "red front", "blue side panels"],
        "books": [
            book("The Glitter Dome", "Joseph Wambaugh", "Mystery / Thriller"),
            book("The Late Show", "Michael Connelly", "Mystery / Thriller"),
            book("Condominium", "John D. MacDonald", "Fiction"),
            book("Stone Cold", "David Baldacci", "Mystery / Thriller"),
            book("Sea Serpent's Heir: Book One", "Mairghread Scott", "Graphic Novel / Fantasy"),
            book("Worst Bot Ever: Meet Ballpoint!", "", "Juvenile Fiction"),
            book("Snowglobe", "", "Fiction"),
            book("The Butcher's Theater", "Jonathan Kellerman", "Mystery / Thriller"),
            book("The Generals", "W.E.B. Griffin", "Historical Fiction"),
            book("The Other Side of Midnight", "Sidney Sheldon", "Fiction"),
            book("Star Wars: Heir to the Empire", "Timothy Zahn", "Science Fiction"),
            book("Ten Big Ones", "Janet Evanovich", "Mystery / Humor"),
            book("Time of Death", "J.D. Robb", "Mystery / Thriller"),
            book("Virgin", "Robin Maxwell", "Historical Fiction"),
            book("Murder of Innocence", "James Patterson", "Mystery / Thriller"),
            book("Worse Than a Lie", "Ben Crump", "Nonfiction"),
            book("Exit Wounds", "J.A. Jance", "Mystery / Thriller"),
            book("Obsession", "Jonathan Kellerman", "Mystery / Thriller"),
            book("Daughter of Fortune", "Isabel Allende", "Historical Fiction"),
            book("The Apple Cart", "George Bernard Shaw", "Drama"),
            book("All That Remains", "Patricia Cornwell", "Mystery / Thriller"),
            book("The Mark", "", "Fiction", confidence=0.55, notes="Partial title visible; author unclear."),
            book("The Tenth Justice", "Brad Meltzer", "Thriller"),
            book("Silent Partner", "Jonathan Kellerman", "Mystery / Thriller"),
            book("Blue at the Mizzen", "Patrick O'Brian", "Historical Fiction"),
            book("The Hundred Days", "Patrick O'Brian", "Historical Fiction"),
            book("The Thirteen-Gun Salute", "Patrick O'Brian", "Historical Fiction"),
            book("Gridlock", "", "Thriller", confidence=0.55, notes="Title visible; author unclear."),
            book("Queen Among the Dead", "Lesley Livingston", "Young Adult Fantasy"),
            book("Open Season", "C.J. Box", "Mystery / Thriller"),
            book("Razor Girl", "Carl Hiaasen", "Fiction / Humor"),
            book("The Missing Guests of the Magic Grove Hotel", "David Casarett", "Mystery"),
        ],
    },
    {
        "library_name": "Panda Roof Civic Little Free Library",
        "library_description": (
            "White panda-painted mini library with blue roof stripes near a red-brick civic or church-like building."
        ),
        "geolocation": {
            "latitude": 39.41461944444444,
            "longitude": -77.42005833333334,
            "source": "photo_exif",
            "confidence": 0.99,
        },
        "place_clues": ["panda drawing", "blue roof stripes", "red brick building", "white columns"],
        "books": [
            book("Fenton Glass: The Second Twenty-Five Years", "William Heacock", "Nonfiction / Collectibles"),
            book("All Kinds of Families", "Norma Simon; Joe Lasker", "Juvenile Nonfiction"),
            book("The Contender", "Robert Lipsyte", "Young Adult Fiction"),
            book("Forty Acres and Maybe a Mule", "Harriette Gillem Robinet", "Juvenile Historical Fiction"),
            book("The Elephant's Child and Other Just So Stories", "Rudyard Kipling", "Juvenile Classics"),
            book("Where's Wendy?", "", "Juvenile Fiction", confidence=0.55),
            book("Sunday with Seurat", "", "Juvenile Nonfiction / Art"),
            book("Snails", "", "Juvenile Nonfiction"),
            book("Grandma Says", "", "Juvenile Fiction", confidence=0.5),
        ],
    },
    {
        "library_name": "Carroll Parkway Tree Little Free Library",
        "library_description": "Shingle-roof wooden Little Free Library mounted beside a large tree and brick house.",
        "charter_number": "25739",
        "charter_registration": registration(
            "matched",
            "25739",
            distance_miles=0.0166357437,
            lfl_id=55057,
            library_name="Laura Fitzgibbon #25739 Frederick MD",
            steward_name="Laura Fitzgibbon",
            street="258 Carroll Parkway",
            city="Frederick",
            state="MD",
            postal_code="21701",
            country="US",
            record_url="https://appapi.littlefreelibrary.org/libraries/55057.json",
        ),
        "geolocation": {
            "latitude": 39.41496111111111,
            "longitude": -77.41798055555556,
            "source": "photo_exif",
            "confidence": 0.99,
        },
        "place_clues": ["large tree", "brick house", "shingle roof", "wooden little library"],
        "books": [
            book("Inheriting His Secret Christmas Baby", "Heidi Betts", "Romance"),
            book("The Sheriff's Christmas Surprise", "Marie Ferrarella", "Romance"),
            book("The Daddy Trap", "Kayla Daniels", "Romance"),
            book("A Weaver Holiday Homecoming", "Allison Leigh", "Romance"),
            book("Kira-Kira", "Cynthia Kadohata", "Juvenile Fiction"),
            book("A View to Die For", "Richard Houston", "Mystery"),
            book("Friday's Child", "Kylie Brant", "Romance / Suspense"),
            book("The Rancher Takes a Family", "Cathy Gillen Thacker", "Romance"),
            book("Will of Steel / Reluctant Father", "", "Romance"),
            book("Those Matchmaking Babies", "", "Romance"),
            book("Santa in a Stetson", "Rebecca Winters", "Romance"),
            book("A Little Christmas Magic", "Sylvie Kurtz", "Romance"),
            book("Make-Believe Mistletoe", "", "Romance"),
            book("Baby Be Mine", "", "Romance"),
            book("The McKettrick Way", "Linda Lael Miller", "Romance", confidence=0.55),
            book("Democratic Designs", "", "Nonfiction", confidence=0.55),
            book("Maison Ikkoku", "Rumiko Takahashi", "Manga", confidence=0.55),
        ],
    },
    {
        "library_name": "Emily Roy Weathered Green Little Free Library",
        "library_description": "Weathered pale-green and wood Little Free Library beside a driveway and leafy tree.",
        "charter_number": "59788",
        "charter_registration": registration(
            "matched",
            "59788",
            distance_miles=0.0134739229,
            lfl_id=2808,
            library_name="Emily Roy #59788 Frederick MD",
            steward_name="",
            street="354 Catoctin Ave.",
            city="Frederick",
            state="MD",
            postal_code="21701",
            country="US",
            record_url="https://appapi.littlefreelibrary.org/libraries/2808.json",
        ),
        "geolocation": {
            "latitude": 39.40589166666666,
            "longitude": -77.42115833333334,
            "source": "photo_exif",
            "confidence": 0.99,
        },
        "place_clues": ["driveway", "blue Subaru", "weathered wooden door", "Take a book or Leave a book sign"],
        "books": [
            book("Spirituality For Dummies", "Sharon Janis", "Religion / Spirituality"),
            book("Swarm", "Scott Westerfeld; Margo Lanagan; Deborah Biancotti", "Young Adult Science Fiction"),
            book("The Moon in the Palace", "Weina Dai Randel", "Historical Fiction"),
            book("The Empress of Bright Moon", "Weina Dai Randel", "Historical Fiction"),
            book("Angel Child, Dragon Child", "Michele Maria Surat", "Juvenile Fiction"),
            book("The Puppets of Spelhorst", "Kate DiCamillo", "Juvenile Fiction"),
            book("Fly Away Home", "Eve Bunting", "Juvenile Fiction"),
            book("Song to Drown Rivers", "Ann Liang", "Historical Fiction"),
            book("Heroes of the Frontier", "Dave Eggers", "Fiction"),
            book("Abraham", "Charles R. Swindoll", "Religion / Biography"),
            book("The Wedding Gift", "Marlen Suyapa Bodden", "Historical Fiction"),
            book("Little Polar Bear Finds a Friend", "Hans de Beer", "Juvenile Fiction"),
            book("Make Way for Ducklings", "Robert McCloskey", "Juvenile Fiction"),
            book("The Power of Now", "Eckhart Tolle", "Self-Help / Spirituality"),
            book("Sins of Omission", "Fern Michaels", "Fiction"),
            book("Jesus Calling", "Sarah Young", "Religion / Devotional"),
            book("Final Justice", "Fern Michaels", "Fiction"),
            book("Purity in Death", "J.D. Robb", "Mystery / Thriller"),
            book("Thursdays at Eight", "Debbie Macomber", "Fiction"),
            book("Plain City", "Virginia Hamilton", "Juvenile Fiction"),
            book("The Au Pairs", "Melissa de la Cruz", "Young Adult Fiction"),
            book("The Murder of the Century", "Paul Collins", "True Crime / History"),
            book("The Demon in the Freezer", "Richard Preston", "Nonfiction / Science"),
            book("A Begonia for Miss Applebaum", "Paul Zindel", "Juvenile Fiction"),
            book("I Will Give You Rest", "", "Religion", confidence=0.55),
            book("Restless Hearts", "Marta Perry", "Romance"),
            book("Seduction in Death", "J.D. Robb", "Mystery / Thriller"),
            book("Ceremony in Death", "J.D. Robb", "Mystery / Thriller"),
            book("WayMaker", "Ann Voskamp", "Religion / Spirituality"),
            book("A CEO Only Does Three Things", "Trey Taylor", "Business"),
            book("John: The Gospel of Light and Life", "Adam Hamilton", "Religion"),
            book("Faith That Overcomes", "Joyce Meyer", "Religion"),
            book("The Universe Is a Green Dragon", "Brian Swimme", "Science / Spirituality"),
            book("God's Promises for Your Life", "", "Religion"),
            book("Naked in Death", "J.D. Robb", "Mystery / Thriller"),
        ],
    },
    {
        "library_name": "Blue White Neighbor Sign Little Free Library",
        "library_description": (
            "Blue-and-white Little Free Library in a front-yard garden under a leafy tree, near a Class of 2026 sign."
        ),
        "geolocation": {
            "latitude": 39.412477777777774,
            "longitude": -77.42895,
            "source": "photo_exif",
            "confidence": 0.99,
        },
        "place_clues": ["Class of 2026 sign", "multilingual neighbor sign", "blue-and-white box", "front yard"],
        "books": [
            book("Make It Make Sense", "Lucy Blakiston; Bel Hawkins", "Juvenile Nonfiction"),
            book("Amal Unbound", "Aisha Saeed", "Juvenile Fiction"),
            book("Inkspell", "Cornelia Funke", "Juvenile Fantasy"),
            book("Winning the Wallflower", "Eloisa James", "Romance"),
            book("The Night Shift", "Alex Finlay", "Thriller"),
            book("Once a Rebel", "Mary Jo Putney", "Historical Romance"),
            book("World Without End", "Ken Follett", "Historical Fiction"),
            book("The Hottest Dishes of the Tartar Cuisine", "Alina Bronsky", "Fiction"),
            book("Man Tiger", "Eka Kurniawan", "Literary Fiction"),
            book("Random Musings", "Julie Gaver", "Essays"),
            book("The Complete Idiot's Guide to Snack Cakes", "", "Cooking / Reference"),
            book("The Complete Idiot's Guide to The Superfood Cookbook", "", "Cooking / Reference"),
            book("Solimar: The Sword of the Monarchs", "Pam Munoz Ryan", "Juvenile Fiction"),
            book("Bonanza Girl", "Patricia Beatty", "Juvenile Fiction"),
            book("How to Make a Plant Love You", "Summer Rayne Oakes", "Gardening / Houseplants"),
            book("The Hurricane Sisters", "Dorothea Benton Frank", "Fiction"),
            book("Hope You're Having a Great Day! I Know I Am!", "Palm Christian", "Inspirational"),
        ],
    },
    {
        "library_name": "Boys and Girls Club Little Free Library",
        "library_description": "Blue and yellow Little Free Library in front of Boys & Girls Club of Frederick County.",
        "charter_number": "132082",
        "charter_registration": registration(
            "location_mismatch",
            "132082",
            error="Public lookup points outside the photographed Frederick location; staged as photo-visible but unverified.",
        ),
        "geolocation": {
            "latitude": 39.40897222222222,
            "longitude": -77.41633888888889,
            "source": "photo_exif",
            "confidence": 0.99,
        },
        "place_clues": ["Boys & Girls Club of Frederick County", "blue and yellow building", "accessible ramp"],
        "books": [
            book("Just Tell Me When We're Dead!", "Eth Clifford", "Juvenile Fiction"),
            book("A Crooked Kind of Perfect", "Linda Urban", "Juvenile Fiction"),
            book("Hour Game", "David Baldacci", "Thriller"),
            book("Long Shadows", "David Baldacci", "Thriller"),
            book("The Persuader", "Lee Child", "Thriller"),
            book("The Woman Who Couldn't Scream", "Christina Dodd", "Romantic Suspense"),
            book("Cradle and All", "James Patterson", "Thriller"),
            book("Judge & Jury", "James Patterson; Andrew Gross", "Thriller"),
            book("Every Last One", "Anna Quindlen", "Fiction"),
            book("The Truth About the Couch", "Adam Rubin; Liniers", "Juvenile Fiction"),
            book("From the Desk of Zoe Washington", "Janae Marks", "Juvenile Fiction"),
            book("Wedding Wings", "Kiki Thorpe", "Juvenile Fiction"),
            book("One Crazy Summer", "Rita Williams-Garcia", "Juvenile Fiction"),
            book("Junie B. First Grader: Aloha-ha-ha!", "Barbara Park", "Juvenile Fiction"),
            book("365 Read-Aloud Bedtime Bible Stories", "", "Religion / Juvenile"),
            book("The Steam Chasers", "Doresa A. Jennings", "Juvenile Fiction"),
            book("What Love Is", "", "Juvenile Fiction", confidence=0.5),
            book("The Christmas Star", "", "Juvenile Fiction", confidence=0.5),
            book("The Wimpy Kid Do-It-Yourself Book", "Jeff Kinney", "Juvenile Humor"),
            book("A Chair for My Mother", "Vera B. Williams", "Juvenile Fiction"),
        ],
    },
    {
        "library_name": "Blue Courtyard Little Free Library",
        "library_description": "Blue Little Free Library on a black post in a grassy courtyard beside red-brick buildings.",
        "geolocation": {
            "latitude": 39.405705555555556,
            "longitude": -77.40837777777779,
            "source": "photo_exif",
            "confidence": 0.99,
        },
        "place_clues": ["blue box", "black post", "grassy courtyard", "red-brick buildings"],
        "books": [
            book("The Mitten", "Jan Brett", "Juvenile Fiction"),
            book("Mister Seahorse", "Eric Carle", "Juvenile Fiction"),
            book("Stephanie's Ponytail", "Robert Munsch", "Juvenile Fiction"),
            book("Best Friends Pretend!", "", "Juvenile Fiction"),
            book("Count!", "Denise Fleming", "Juvenile Fiction"),
            book("Dog Days", "", "Juvenile Fiction"),
            book("Peppa Pig: Touch and Feel Class Pet", "", "Juvenile Fiction"),
            book("Love You Forever", "Robert Munsch", "Juvenile Fiction"),
            book("Every Last One", "Anna Quindlen", "Fiction"),
            book("Goodnight Goon: A Petrifying Parody", "Michael Rex", "Juvenile Fiction"),
            book("English Grammar Drills", "Mark Lester", "Reference / Language"),
            book("Chicka Chicka Boom Boom", "Bill Martin Jr.; John Archambault; Lois Ehlert", "Juvenile Fiction"),
            book("Baby Animals First 123 Book", "", "Juvenile Board Book"),
            book("No Matter What", "Debi Gliori", "Juvenile Fiction"),
            book("Baby Animals First ABC Book", "", "Juvenile Board Book"),
        ],
    },
    {
        "library_name": "Mint Green Sidewalk Little Library",
        "library_description": "Mint-green handmade sidewalk mini library with flower trim and pebble chimney near a rowhouse stoop.",
        "geolocation": {
            "latitude": 39.410330555555554,
            "longitude": -77.41133888888889,
            "source": "photo_exif",
            "confidence": 0.99,
        },
        "place_clues": ["mint green", "flower trim", "pebble chimney", "rowhouse sidewalk"],
        "books": [
            book("Mirror Image", "Tom Clancy; Steve Pieczenik", "Thriller"),
            book("Before I Say Goodbye", "Mary Higgins Clark", "Mystery / Thriller"),
            book("Merci Suarez Can't Dance", "Meg Medina", "Juvenile Fiction"),
            book("Hot and Sticky BBQ", "Ted Reader", "Cooking"),
        ],
    },
    {
        "library_name": "Green Purple Rowhouse Little Free Library",
        "library_description": "Green and purple Little Free Library on a brick sidewalk among rowhouses and purple planters.",
        "charter_number": "78906",
        "charter_registration": registration("not_found", "78906"),
        "geolocation": {
            "latitude": 39.41208888888889,
            "longitude": -77.41445277777778,
            "source": "photo_exif",
            "confidence": 0.99,
        },
        "place_clues": ["brick sidewalk", "rowhouses", "purple flowers", "green and purple cabinet"],
        "books": [
            book("Roadside America", "Kirby; Smith; Wilkins", "Travel / Americana"),
            book("The Curious Charms of Arthur Pepper", "Phaedra Patrick", "Fiction"),
            book("Superfan", "Jenny Tinghui Zhang", "Fiction"),
            book("The Ending Writes Itself", "Evelyn Clarke", "Fiction"),
            book("Quarter Queen", "Kayla Hardy", "Fiction"),
            book("Boleyn Traitor", "Philippa Gregory", "Historical Fiction", confidence=0.65),
            book("Daydream", "Hannah Grace", "Romance"),
            book("The Secret Lives of Murderers' Wives", "Elizabeth Arnott", "Thriller"),
            book("Widow", "T. Kira Madden", "Fiction"),
            book("The Fox Hunt", "Caitlin Breeze", "Thriller"),
            book("Red Dog Farm", "Nathaniel Ian Miller", "Fiction"),
            book("The Lowland", "Jhumpa Lahiri", "Fiction"),
            book("Myths, Illusions, & Peace", "Dennis Ross; David Makovsky", "Politics / History"),
            book("One & Only", "Maurene Goo", "Young Adult Fiction"),
            book("Looking for Alaska", "John Green", "Young Adult Fiction"),
            book("Hex House", "Jamie Stewart", "Horror"),
            book("Metal", "Morgan Jenkins", "Fiction"),
            book("Quartet", "James McKean", "Poetry / Fiction"),
            book("Silent No Longer", "Robert Stack", "Nonfiction"),
            book("Say You'll Remember Me", "Abby Jimenez", "Romance"),
        ],
    },
    {
        "library_name": "New Wooden Rowhouse Little Free Library",
        "library_description": "New natural-wood Little Free Library by a rowhouse stoop near house number 214.",
        "charter_number": "217939",
        "charter_registration": registration("not_found", "217939"),
        "geolocation": {
            "latitude": 39.410869444444444,
            "longitude": -77.41530555555556,
            "source": "photo_exif",
            "confidence": 0.99,
        },
        "place_clues": ["house number 214", "natural wood", "rowhouse stoop", "white railing"],
        "books": [
            book("While Justice Sleeps", "Stacey Abrams", "Thriller"),
            book("Simon the Fiddler", "Paulette Jiles", "Historical Fiction"),
            book("The Rising Tide", "Ann Cleeves", "Mystery"),
            book("Winter Chill", "Joanne Fluke", "Mystery"),
            book("Skating Over the Line", "Joelle Charbonneau", "Mystery"),
            book("Elsewhere", "Gabrielle Zevin", "Young Adult Fiction"),
            book("Harry Potter and the Deathly Hallows", "J.K. Rowling", "Fantasy"),
            book("Hope for a Woman's Heart", "", "Religion / Inspirational"),
            book("Hatchet", "Gary Paulsen", "Juvenile Fiction"),
            book("Miss Mary Mack", "Mary Ann Hoberman", "Juvenile Fiction"),
            book("Inside a House That Is Haunted", "", "Juvenile Fiction"),
            book("Day Shift", "Charlaine Harris", "Fantasy / Mystery"),
            book("A House Full of Daughters", "Juliet Nicolson", "Memoir / History"),
        ],
    },
    {
        "library_name": "Downtown Frederick Purple Porch Little Free Library",
        "library_description": (
            "Purple Little Free Library on a porch-side sidewalk in downtown Frederick, near rowhouses and a pride flag."
        ),
        "charter_number": "126461",
        "charter_registration": registration(
            "matched",
            "126461",
            distance_miles=0.003536788469299359,
            lfl_id=37517,
            library_name="Little Free Library (Downtown Frederick) #126461 Frederick MD",
            steward_name="",
            street="15 McMurray St",
            city="Frederick",
            state="MD",
            postal_code="21701",
            country="United States",
            latitude=39.4101153,
            longitude=-77.4150581,
            record_url="https://appapi.littlefreelibrary.org/libraries/37517.json",
        ),
        "geolocation": {
            "latitude": 39.410158333333335,
            "longitude": -77.41502222222223,
            "source": "photo_exif",
            "confidence": 0.99,
        },
        "place_clues": ["purple cabinet", "porch", "brick sidewalk", "rowhouses", "pride flag", "charter 126461"],
        "books": [
            book("Girl, Stolen", "April Henry", "Young Adult Thriller"),
            book("Inkheart", "Cornelia Funke", "Juvenile Fantasy"),
            book(
                "An Indigenous Peoples' History of the United States for Young People",
                "Roxanne Dunbar-Ortiz",
                "History / Young Readers",
            ),
            book("Hikaru no Go", "Yumi Hotta; Takeshi Obata", "Manga", confidence=0.65),
            book("Shiver: Selected Stories", "Junji Ito", "Manga / Horror"),
            book("Perfume: The Story of a Murderer", "Patrick Suskind", "Fiction"),
            book("No-Drama Discipline", "Daniel J. Siegel; Tina Payne Bryson", "Parenting"),
            book("The Queen's Fool", "Philippa Gregory", "Historical Fiction"),
            book("In the Time of the Butterflies", "Julia Alvarez", "Historical Fiction"),
            book("The Boleyn Inheritance", "Philippa Gregory", "Historical Fiction"),
            book("The Skeptic's Guide to the Universe", "Steven Novella", "Science / Skepticism"),
            book("The Other Queen", "Philippa Gregory", "Historical Fiction"),
            book("How to Talk to a Science Denier", "Lee McIntyre", "Science / Society"),
            book("People of Means", "Nancy Johnson", "Fiction"),
            book("The Omnivore's Dilemma: Young Readers Edition", "Michael Pollan", "Food / Nonfiction"),
            book("Healthy Sleep Habits, Happy Child", "Marc Weissbluth", "Parenting"),
            book("An Almost Perfect Moment", "Binnie Kirshenbaum", "Fiction"),
            book("The Huntress", "Kate Quinn", "Historical Fiction"),
            book("You Shall Know Our Velocity", "Dave Eggers", "Fiction"),
            book("Spot Can Count", "Eric Hill", "Juvenile Fiction", confidence=0.55),
        ],
    },
    {
        "library_name": "Red Woods Trail Empty Little Library",
        "library_description": (
            "Large red double-door Little Free Library in a wooded trail setting. "
            "The current upload shows zero books inside."
        ),
        "geolocation": {
            "latitude": 38.93531944444444,
            "longitude": -77.28199722222222,
            "source": "photo_exif",
            "confidence": 0.99,
        },
        "place_clues": ["wooded trail", "red double doors", "empty shelves"],
        "books": [],
    },
]


def existing_library_id(payload: dict[str, Any]) -> int | None:
    charter = app.normalize_charter_number(payload.get("charter_number"))
    lat = payload["geolocation"]["latitude"]
    lon = payload["geolocation"]["longitude"]
    with app.get_connection() as connection:
        if charter:
            row = connection.execute(
                "SELECT id FROM libraries WHERE charter_number = ? ORDER BY id DESC LIMIT 1",
                (charter,),
            ).fetchone()
            if row:
                return int(row["id"])
        rows = connection.execute(
            """
            SELECT id, latitude, longitude
            FROM libraries
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
            """
        ).fetchall()
        for row in rows:
            if app.haversine_miles(lat, lon, float(row["latitude"]), float(row["longitude"])) <= 0.03:
                return int(row["id"])
    return None


def main() -> None:
    app.initialize_database()
    created = 0
    updated = 0
    for payload in LIBRARIES:
        existing_id = existing_library_id(payload)
        import_payload = dict(payload)
        import_payload["replace_inventory"] = True
        if existing_id:
            import_payload["library_id"] = existing_id
            updated += 1
        else:
            created += 1
        app.insert_library(import_payload)

    print({"created": created, "updated": updated, **app.get_counts()})


if __name__ == "__main__":
    main()
