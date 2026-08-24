from bs4 import BeautifulSoup

with open("practice_jobs.html", "r", encoding="utf-8") as file:
    html = file.read()

soup = BeautifulSoup(html, "html.parser")

jobs = soup.find_all("div", class_="job")

job_list = []

for job in jobs:
    title = job.find("h2").text
    company = job.find("p", class_="company").text
    location = job.find("p", class_="location").text

    job_data = {
        "title": title,
        "company": company,
        "location": location
    }

    job_list.append(job_data)

print(job_list)