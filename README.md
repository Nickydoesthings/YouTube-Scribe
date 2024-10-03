# ABOUT:

YouTube Scribe is a web application designed to quickly generate detailed written summaries and tutorials from YouTube videos. The app analyzes YouTube captions (or transcribes audio) to provide you with an easy-to-follow guide.

Using the web app is as simple as pasting in a URL - YouTube scribe handles the rest and outputs a written tutorial based on the content video. All in just seconds :)

This app relies heavily on OpenAI's ChatGPT API to turn captions into readable instructions. So, you'll need to bring your own API key. More info on that here: [OpenAI Quickstart](https://platform.openai.com/docs/quickstart).

Simply paste your API key into the `.env` file, and you're good to go.

Cost-wise, it's pretty cheap! Generally less than 1 cent per use (unless transcription is required, which may be slightly more expensive—but that is very rare).

The website includes a non-functional account system where users could sign up and log in. This can be ignored, as it won't work unless it's connected to the internet and requires my Brevo API key to send confirmation emails. You don't need to sign in to use any of the main features.

# CONTEXT:

YouTube Scribe was originally designed to be a standalone website, but I ran into some issues with YouTube bot detection when hosting on a public web server, ultimately killing the project as a public product. When you run this app, it should launch from a development server on your local machine, and the bot detection issue should not be a problem for you.

Please feel free to do what you wish with this repo, as I have no plans of continuing the project. It was a great learning experience and my first time using Flask and the OpenAI API. A large part of this codebase was created using LLMs as I worked to integrate them into my workflow.

Made by Nicky Z in 2024.
