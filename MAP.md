
1. The apps and what each owns. Four apps, one or two sentences each.

    The accounts app owns identity, sign-in/out and signup from accounts/views.py, and accounts/mixins.py. The identity portion encompasses the accounts.User model which allows the different roles appropriate access (customers, employees, admins), and the accounts/mixins.py has a StaffRequiredMixin which acts as the gateway to the back-office view.
    The products app owns the catalog (Category, Product, and Tag from products/models.py), the ProductQuerySet which contains available() and search() methods, and the seed command which allows us to seed our database. This app houses the website's home page, other detail pages, and staff CRUD screens (explained later in additional questions asked).
    The orders app owns the transaction path, which has four models -- Cart, CartItem, Order, and OrderItem in orders/models.py. This app allows users to manage their cart and checkout.
    The dashboard app owns the staff analytics view and is the only app with no models. It gets all of its analytical information from orders and queries this information into usable data.

2. The path of one request. From browser to rendered page for the home page /, naming the files: the URL pattern, the view, and the template.

    For this example, I'll use the path to the home page. First, Django searches the urls in config/urls.py. It finds the url prefix that matches the requested / page and then searches inside of it to ensure the inner routes match. In this case, it is path("", include("products.urls")) in config/urls.py and path("", views.CatalogView.as_view(), name="catalog") in products/urls.py. The homepage is therefore products:catalog.
    The view is products.views.py, and the template used is templates/products/catalog.html

3. A model you read. Pick the Cart or User model from Step 6. In one or two sentences, say what it represents and name one method or field in it that was new or interesting to you.
    The Cart model allows a cart to be created for each user using 5 methods that give us the username for each cart for the admin and shell and allow us to add products, manage items counts, line items, and the total cost of the cart. I found the for_user(user) method to be very interesting because it only creates a cart for a user once they actually access it. Before it is touched, no cart for that user exists making it so that our cart code does not have to include null-checking. I honestly would have thought that the cart would be created for each user upon signup, and it lead me to wonder how we handle creating a cart for a user that is not yet signed in (I discuss this a bit in the additional questions.)

4. Deleting a category. Products belong to categories through a ForeignKey. State what happens to a category's products when the category is deleted, and name the line of code that decides.

    The products are not affected because delete is refused. This is due to line 70 in products/models.py -- on_delete=models.PROTECT inside the Product.category ForeignKey. Basically, this says that if we try to delete a category that still contains products, stop the deletion altogether and display an error message. This protects us from irreversible deletion that could accidentally occur in the back-office if we would have used something like CASCADE, which is what we have practiced so far in the course. 

5. Where the tests live. How the suite is organized and what conftest.py provides.
    Tests are configured in pyproject.toml through pytest and pytest-django, and the tests live inside each app. confest.py lives at the project root and is available to all 4 apps. This allows pytest to share fixtures, which are automatically available to every test in its directory and below with no import required.

6. One thing you're still working to understand. Name one part of this codebase you do not fully understand yet. If everything is clear, name the part that took the most work to understand. Then describe what you did to get a handle on it: a follow-up you asked the agent, a file you opened, a small test you ran. Say where you ended up. You do not lose points for still being unsure. This section grades the attempt, not whether you solved it.

    There is so much in this codebase that is new to me and initially threw me for a loop. However, each time I read through the AI's explanations, the new concepts started to make more sense. In light of this, I asked the agent what it thought the most difficult portion of the codebase would be from a beginner's viewpoint, and it surely delivered. It generated a whole bunch of hard concepts from being unable to see the logic behind class-based views to the hardest function in the codebase -- revenue_over_time(). Reading through its explanations were helpful and gave me a lot of insight into understanding code that might not make sense otherwise. However, what was most valuable to me was its recommendation of how to understand this project as a beginner.
    The agent recommended the following to me:

    "If I were onboarding someone, I'd recommend these actions. Read in this order, because each layer only needs the one below it: products/models.py → orders/models.py → orders/validators.py (pure functions, genuinely easy) → orders/services.py (procedural, well-documented) → products/views.py → the HTMX partials → dashboard/queries.py last.

    And read the tests alongside — orders/test_services.py and orders/test_validators.py are the best documentation in the repo. The codebase is unusually well-commented for a student project; the docstrings on both deep modules explain why, not just what, which removes a lot of the difficulty that would otherwise be there."

    So, that's what I did. I followed the AI's recommendation and explored the path suggested and asked questions along the way. I can't say that I fully understand this project, but I think I have more insight.

    For example, at the beginning of my exploration I did not understand the function of the Meta class in products/models.py, so I asked the agent to explain it. The agent explained that it is the inner configuration class that allows us to confgigure settings like default ordering, table name, constraints, etc -- basically anything that is not a field. in Category.Meta this allows us to do things like sort our category alphabetically and change the plural form of category to categories rather than categorys which is what Django would default to. Now I understand the purpose of the Meta class and can apply my understanding to other places it is used throughout the project. 


7. Three questions of your own.

    1. You stated that the for_user(user) does not create a cart until someone actually touches it. How are carts created for users that are not signed up or signed in?
    By asking this question, I learned that users without an account (called anonymous visitors) are unable to add items to their cart. Since Cart.user is a non-nullable OneToOneField to AUTH_USER_MODEL, a cart cannot be created without a user associated to it. Therefore, if an anonymous visitor tried adding an item to their cart or selecting the cart, they would be redirected to login or signup.

    2.  What do you mean by slug-based detail pages and CRUD screens?
        I found out that slug is a URL-safe text indentifier. It comes from SlugField, which is a CharField that uses letters, numbers, hyphens, and underscores. By setting unique=True, it means that the text in the SlugField will only match up to one product, so we can use this tet as an identifier instead of the database primary key. The standard is for public facing URLs to use slugs and for back-office URLs to use primary keys.
        CRUD stands for Create, Read, Update, and Delete, which are the four basic operations on a record. CRUD screens refer to the pages that our staff use to execute these functions on the catalog (our back-office pages).

        3.  When describing confest.py, you said its docstring states the rule — "Shared test data lives here as plain fixtures — no factories." No factory-boy, per CLAUDE.md; just functions returning real model instances. What do you mean by plain fixtures, factories, and factory-boy?
        -A fixture is a function that pytest uses to run tests that return a value. The plain fixture returns one finished product with hardcoded values -- the same output each time the test is run (assuming it passes).
        -Conversely, a factory builds objects to order and returns a function instead od a model. The test specifies the parameters and the factory fills them in. It is not harcoded and could have different outputs.
        -factory-boy is the library that populates factories based on the parameters defined. It is a third-party package.
    I learned that factories are useful for larger projects. It is not in our project, which makes sense because this is our first project for the semester and its not really big enough to warrant the use of factories. Using fixtures allows every test and its parameters to be visible in the code, which will be helpful as we are just starting out. We can expect the output of each passing test, we do not have to worry about the chance of nondeterminism occuring and producing bugs. 
