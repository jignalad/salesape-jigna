
Hello!

Here's a raw summary of my thought process working through this project.

1. I followed the set up and run instructions and immediately ran into 502s on the API. I did some debugging and saw that a deprecated version of googles genai package was being used. So I asked the cursor agent to swap the usage to the new version and also updated the default model version to use. Because the API contract is different for the new genai library, we had some code cleanup so I asked AI for that as well.

2. Now getting to the prompt. I gave the cursor agent a detailed promt to add the feedback mechanism to the chat.

3. I tested out what the AI created and noticed a few bugs in the UX:
    - there is a bug where the frontend shows user submitted messages twice while in the chat window. please fix it
    - when a user is attempting to submit feedback in the UI, the chat scrolls to the top message instead of staying pinned on the last message that is being given feedback

4.  Once the bugs were addressed I noticed that some of the chat UI was in an incomplete state like the ability to name chats. So I asked AI to finish that feature.

5. Now that we can submit and reference feedback we can work on adding the insights UI. I gave the cursor agent a few prompts to add a Usage tab with a handful of metrics and to iterate on the UX in that page.

6.  I also noticed that the AI response text was markdown formatted but not applying styling, so I asked the cursor agent to use a package compatible with vanilla js to format the UI.

7. At this point things were working well. I wanted to give the app some more style so I gave cursor agent some style inspuration to update with.

8. Expanding on the metrics tab, I thought it would be cool to repurpose the gemini integration to generate an AI summary of the metrics. 

9. Upon adding this feature, I prompted for a few cleanup steps on the repo and adding test coverage.

10. Coming up on time this is where I wrapped up.

What I would do with more time to improve this chat app

1. Integrate a charting library to show more insights like trends over time on feedback.

2. Adding progressive loading of the AI response and implement full streaming to give a more natural chat like experience.

3. Add security and auth to the application along with application rate limiting and better error handling.

4. Conversation search/filtering- as conversations grow users may want to find old conversations.

5. Prompt templating and management. Save some premade prompts and leverage prompt templates that improve based on the usage insights and feedback.



Hello!

Here's a raw summary of my thought process working through this project.

1. I followed the set up and run instructions and immediately ran into 502s on the API. I did some debugging and saw that a deprecated version of googles genai package was being used. So I asked the cursor agent to swap the usage to the new version and also updated the default model version to use. Because the API contract is different for the new genai library, we had some code cleanup so I asked AI for that as well.

2. Now getting to the prompt. I gave the cursor agent a detailed promt to add the feedback mechanism to the chat.

3. I tested out what the AI created and noticed a few bugs in the UX:
    - there is a bug where the frontend shows user submitted messages twice while in the chat window. please fix it
    - when a user is attempting to submit feedback in the UI, the chat scrolls to the top message instead of staying pinned on the last message that is being given feedback

4.  Once the bugs were addressed I noticed that some of the chat UI was in an incomplete state like the ability to name chats. So I asked AI to finish that feature.

5. Now that we can submit and reference feedback we can work on adding the insights UI. I gave the cursor agent a few prompts to add a Usage tab with a handful of metrics and to iterate on the UX in that page.

6.  I also noticed that the AI response text was markdown formatted but not applying styling, so I asked the cursor agent to use a package compatible with vanilla js to format the UI.

7. At this point things were working well. I wanted to give the app some more style so I gave cursor agent some style inspuration to update with.

8. Expanding on the metrics tab, I thought it would be cool to repurpose the gemini integration to generate an AI summary of the metrics. 

9. Upon adding this feature, I prompted for a few cleanup steps on the repo and adding test coverage.

10. Coming up on time this is where I wrapped up.

What I would do with more time to improve this chat app

1. Integrate a charting library to show more insights like trends over time on feedback.

2. Adding progressive loading of the AI response and implement full streaming to give a more natural chat like experience.

3. Add security and auth to the application along with application rate limiting and better error handling.

4. Conversation search/filtering- as conversations grow users may want to find old conversations.

5. Prompt templating and management. Save some premade prompts and leverage prompt templates that improve based on the usage insights and feedback.

6. I would also spend more time reviewing the effectiveness of test coverage.


- Jigna

