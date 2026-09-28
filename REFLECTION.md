## Featured Products. 

Question 1 - Trace the feature. Explain how marking a product as featured in the admin interface causes the badge to appear in the storefront. Explain the files involved and the code logic. 

    First, we added an is_featured field to products/models.py and making the migrations to the database. Then we added if statements to the products/catalog and products/detail templates that display the badge if_featured = True. By checking the featured box in the admin interface, the boolean becomes True, so when the if statements run, the badge is displayed in the catalog and product detail pages.


Question 2 - How you verified it. Describe how you confirmed the feature works. Name the pages you checked in the browser.

    I verified the featured worked by running the existing tests, reviewing the ones created by the agent, and verifying that the tests passed. I verified that the featured box appeared for products in Django's admin page and selected it for the necessary products. I then checked the catalog page and product detail page to ensure that the badge was displayed.

Question 3 - Judgement. Describe one challenge, unexpected result, or edge case you encountered. Explain what you did to troubleshoot it.

    I think I got lucky this time and did not run into any challenges with the agent. I gave pretty straightforward prompts based on the assignment instructions, and the agent followed up with good, working code. The agent did suggest several additions to my code that I think could have been useful such as a featured products section in the catalog, but I did not explore them as I was not sure what extras would be acceptable for this homework. At the end, I did go back and edit the badge to standout more. Initially it was just plain with a blue background that did not stand out much. I changed it to be pink with a star similar to the assignment. It did not really turn out looking pink, which the agent stated when it logged the prompt, so I did have to ask it to change the color again. I explained the exact shade of pink I wanted the badge to be, and the agent hardcoded that color in rather than using a preset hue from tailwind. 


##Discount Coupons

    Question 1 - One decision from grill me. Choose one /grill-me question that led to an important design decision. If you disagreed with the agent's recommendation, explain what it recommended, why you rejected that recommendation, what you chose instead, and how your choice affected the feature. If you did not disagree with any recommendation, choose a question that was confusing. Explain what you did not understand, the follow-up question(s) you asked, and how you ultimately decided.

    The agent asked me what kind of discount the coupon should give -- percentage, fixed amount, or both. It recommended percentage only, but I chose to go with both percentage and fixed amount. I chose to do this because realistically, our marketing department will likely want to run different kinds of deals to keep customers enagaged and more importantly ensure that we are effectively managing discounts redeemed so we can maximize our revenue and avoid losing money. Because I made this choice, the agent had to go through extra setps to determine how the math at checkout would work. We had to set a floor so the discount would never take the customer total below zero, implement minimum-spend options, add several scenarios to the seed, and create multiple tests to verify the new features worked correctly from all interfaces. If we would have gone with the agent's option, we would have only needed one extra field, rule, and line of maths. 



    Question 2 - The change. Explain the change you made after reviewing the feature. Describe your original choice, what the browser showed you, why you wanted to change it, and how the fix works. If any existing test failed during your build, name it and say what you did about it.

    I honestly liked what the AI built for the most part, but I did opt to make the section where the coupon was applied more visible. Before the change, the section to add the coupon was written in small grey lettering reading "Have a coupon code?" and it was not very visible to someone who might be checking out in a hurry. I decided to make that text as well as the apply button blue so it would be more visible to customers. The fix was simple -- just a change in the html. 
