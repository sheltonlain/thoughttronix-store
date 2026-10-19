## Account Security Center
Question 1 - Review one phase. 

Once Phase 3 was implemented, a forgot password link should be available on the sign in page. When the link is clicked, a reset password link will be emailed if the user has a verfied email address on file. This link allows you to create a new password. When the agent finished writing the code and the new tests for phase 3, I verified what it said it had done against my original requirements. Once I confirmed that matched, I asked for steps on how to manually verify the changes and walked through them. The sign in page did have the forogt password link that emailed a reset link. However, when I clicked on the reset link from the email body in the terminal, the page that popped up told me the link was invalid because it had already been used, was incorrect, or was expired. I told the agent about the error that I found, and upon further investigation, it was determined that the link was so long that it was wrapping into the next line of the terminal, joined by the '=' sign. The fix for this was to go in and delete the '=' when following the link, and then it worked as origianlly outlined. It was determined that if the link were to be sent to an active email address, this would not be an issue as the wrapping would not apply or be conjoined with the '=' in that scenario. The agent did suggest that it could create a shortened link specifically for tests, but I did not want to muddy up my codebase by adding an extra step that would not match the same type of link that would be actually sent out to verified emails. I simply chose to remember to remove the '=' for my remaining manual tests. If multiple people other than myself and the agent frequently worked on this codebase, I probably would have opted to implement the shorter link to avoid this issue in the future. Once determining the fix for the link, I walked through the rest of the steps to ensure that the reset password link worked as I had originally outlined. For example, I made sure that any verified email (not case sensitive) received the link, I could set a new password that followed the password requirements, and I could sign in with the new password. I also created an .env that set the link as already being active for an hour, and made sure that it was disabled after that time (I deleted .env afterwards). I also made sure that you could not use the same link twice, and any passwr=ord reset request got a warning sent to the user's exiting email telling them that a password reset was requested. I also ran the test suite to ensure that all tests passed. 

Question 2 - Authentication code versus the lesson. Identify two Django authentication components used in your completed Account Security Center. For each component, name the exact file where it appears, describe or quote the relevant line of code, and explain what the component does. Then explain how the implementation matches the authentication pattern from the lesson. Reopen Understanding Authentication. 



Question 3 - Password management versus the lesson.

The code that allows password changes is located in accounts/views.py in lines 137-152. It uses Django's built-in PasswordChangeView, which passes the user to the ChangePasswordForm in accounts/forms.py, lines 90-97. The form checks the old password, validates the new password, and stores the new password correctly. Once the password change is complete, PasswordChangeView also sends a message to the verified email address on file alerting the user that their password has been changed. PasswordChangeDoneView is not used in our codebase. Instead, PasswordChangeView redirects the user to the Security Center once their password change is complete (line 146 - success_url = reverse_lazy("accounts:security")). The user is logged out of any other sessions, but the current session is still active and shows the success message, "Password changed. Your other sessions have been signed out." I chose to implement this feature so the user would not have to login again as they would with the PasswordChangeDoneView. Since accounts require a verified email address, the account remains secure as an email alert goes out each time a change happens to the account. 

Question 4 - The tracer-bullet plan. 

All of my tracer-bullets were set to build upon each other through each phase, which broke the plan down into manageable, verifiable chunks without having to backtrack and add changes to a previous phase. For example, Phase 1 handled any accounts with an exiting email that had not yet been verified or that wer missing email addresses, and it automatically marked the seed emails as verified to prevent issues in the future. Additionally, this phase set up the security center in our app with an email card and a password card. The email card showed that the email was either verified or showed a warning encouraging the user to verify it. The password card read that users would soon be able to change their passwords here. By stopping here, we ensured that the phase stayed manageable with a visible result at the end. I could easily verify that the correct features were implemented by running the test suite and performing a reasonable amount of manual verification steps. This made moving to the next phase easy because the groundwork was laid, and I could see the features being added and test them one by one. Since they all built on each other, it was easy to see where we started compared to the finished project. That said, when we added the change password feature in phase 2, I could see the password card being updated and follow the logic behind it to ensure it functioned properly and sent the proper warning email. That set me up for the next feature, which was the forgot password link on the sign up page. Some of the logic from phase 2 was resued to make this feature run, and I had another tangible product at the end. 

## Product Images

Question 1 - One decision from grill me. 

When the agent and I were deciding how the product images should be displayed, it outlined multiple options including cropping each image to a certain size, which sounded like a good option at first. However, upon further investigation, I found out that uploaded images would be autocropped with no control or input by employees uploading them, and the only way to fix errors would be to resumbit a precropped image that looks the exact way you want it. This would have led to tops/bottoms of images being cutoff and would have made it a hassle to fix. I still wanted my images to be uniform across the catalog, so I opted to display the full image within a 4:3 frame and filled in with a background anywhere the image did not naturally fit. I was worried this might come out looking wonky too, but we opted to center the images and fill in the blank space with a color that matches our night theme, so it ultimately worked out in the end. One mistake I did make was keeping the same tailwind server running from start to end. Since it was never rebuilt and I was running an older tailwind version, the images did not load into that 4:3 window like I had requested. I asked the agent to fix this issue, and they did not find an error in the code, which is when I realized the old tailwind server was probably my mistake. However, I opted to have the agent go ahead and hardcode image size into the product list, product page, cart, and back office to avoid this issue in the future. 

Question 2 - Find the upload code.

products/models.py
line 79
image = models.ImageField(upload_to="products/", blank=True)

upload_to places the image inside a products subfolder and defines the database value as products/file_name.jpg (for example).

templates/products/manage_product_form.html
line 13
<form method="post" enctype="multipart/form-data" class="mt-2 space-y-4">

This tells the browser that the form includes a file. Without it, files cannot be uploaded properly. 


Question 3 - Follow the upload process. 

On disk: media/products/dream-sync.webp
MEDIA_ROOT determines this path as BASE_DIR points to "media" and combines it with the database value, which is products/dream-sync.webp, giving us the path shown above.

In database: products/dream-sync.webp
The line image = models.ImageField(upload_to="products/") determines this path. Specifically "upload_to" which uploads the image to a products subfolder. The database value begins with "products/" as specified, followed by the filename (which is automatically slugged in our webapp if the name is unsuitable. In this case I uploaded the image and named it appropriately as dream-sync.webp)

URL: /media/products/dream-sync.webp
MEDIA_URL determines this path. It points to "media/" and combines it with the database value, which is products/dream-sync.webp, which gives us the path listed above.

The media URL pattern in config/urls.py line 27 allows our URL to run during development: 

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

According to what we learned in our lesson, this line of code connects URLS beginning with MEDIA_URL to files stored under MEDIA_ROOT. However, this will only run in the development server as DEBUG is not built for production. 


## Featured Products. 

Question 1 - Trace the feature. Explain how marking a product as featured in the admin interface causes the badge to appear in the storefront. Explain the files involved and the code logic. 

    First, we added an is_featured field to products/models.py and making the migrations to the database. Then we added if statements to the products/catalog and products/detail templates that display the badge if_featured = True. By checking the featured box in the admin interface, the boolean becomes True, so when the if statements run, the badge is displayed in the catalog and product detail pages.


Question 2 - How you verified it. Describe how you confirmed the feature works. Name the pages you checked in the browser.

    I verified the featured worked by running the existing tests, reviewing the ones created by the agent, and verifying that the tests passed. I verified that the featured box appeared for products in Django's admin page and selected it for the necessary products. I then checked the catalog page and product detail page to ensure that the badge was displayed.

Question 3 - Judgement. Describe one challenge, unexpected result, or edge case you encountered. Explain what you did to troubleshoot it.

    I think I got lucky this time and did not run into any challenges with the agent. I gave pretty straightforward prompts based on the assignment instructions, and the agent followed up with good, working code. The agent did suggest several additions to my code that I think could have been useful such as a featured products section in the catalog, but I did not explore them as I was not sure what extras would be acceptable for this homework. At the end, I did go back and edit the badge to standout more. Initially it was just plain with a blue background that did not stand out much. I changed it to be pink with a star similar to the assignment. It did not really turn out looking pink, which the agent stated when it logged the prompt, so I did have to ask it to change the color again. I explained the exact shade of pink I wanted the badge to be, and the agent hardcoded that color in rather than using a preset hue from tailwind. 


## Discount Coupons

    Question 1 - One decision from grill me. Choose one /grill-me question that led to an important design decision. If you disagreed with the agent's recommendation, explain what it recommended, why you rejected that recommendation, what you chose instead, and how your choice affected the feature. If you did not disagree with any recommendation, choose a question that was confusing. Explain what you did not understand, the follow-up question(s) you asked, and how you ultimately decided.

    The agent asked me what kind of discount the coupon should give -- percentage, fixed amount, or both. It recommended percentage only, but I chose to go with both percentage and fixed amount. I chose to do this because realistically, our marketing department will likely want to run different kinds of deals to keep customers engaged and more importantly ensure that we are effectively managing discounts redeemed so we can maximize our revenue and avoid losing money. Because I made this choice, the agent had to go through extra steps to determine how the math at checkout would work. We had to set a floor so the discount would never take the customer total below zero, implement minimum-spend options, add several scenarios to the seed, and create multiple tests to verify the new features worked correctly from all interfaces. If we would have gone with the agent's option, we would have only needed one extra field, rule, and line of maths. 



    Question 2 - The change. Explain the change you made after reviewing the feature. Describe your original choice, what the browser showed you, why you wanted to change it, and how the fix works. If any existing test failed during your build, name it and say what you did about it.

    I honestly liked what the AI built for the most part, but I did opt to make the section where the coupon was applied more visible. Before the change, the section to add the coupon was written in small grey lettering reading "Have a coupon code?" and it was not very visible to someone who might be checking out in a hurry. I decided to make that text as well as the apply button blue so it would be more visible to customers. The fix was simple -- just a change in the html. 

