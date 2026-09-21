## Featured Products. 

Question 1 - Trace the feature. Explain how marking a product as featured in the admin interface causes the badge to appear in the storefront. Explain the files involved and the code logic. 

    First, we added an is_featured field to products/models.py and making the migrations to the database. Then we added if statements to the products/catalog and products/detail templates that display the badge if_featured = True. By checking the featured box in the admin interface, the boolean becomes True, so when the if statements run, the badge is displayed in the catalog and product detail pages.


Question 2 - How you verified it. Describe how you confirmed the feature works. Name the pages you checked in the browser.

    I verified the featured worked by running the existing tests, reviewing the ones created by the agent, and verifying that the tests passed. I verified that the featured box appeared for products in Django's admin page and selected it for the necessary products. I then checked the catalog page and product detail page to ensure that the badge was displayed.

Question 3 - Judgement. Describe one challenge, unexpected result, or edge case you encountered. Explain what you did to troubleshoot it.

    I think I got lucky this time and did not run into any challenges with the agent. I gave pretty straightforward prompts based on the assignment instructions, and the agent followed up with good, working code. The agent did suggest several additions to my code that I think could have been useful such as a featured products section in the catalog, but I did not explore them as I was not sure what extras would be acceptable for this homework. At the end, I did go back and edit the badge to standout more. Initially it was just plain with a blue background that did not stand out much. I changed it to be pink with a star similar to the assignment. It did not really turn out looking pink, which the agent stated when it logged the prompt, so I did have to ask it to change the color again. I explained the exact shade of pink I wanted the badge to be, and the agent hardcoded that color in rather than using a preset hue from tailwind. 