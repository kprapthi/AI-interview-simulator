document.addEventListener("DOMContentLoaded", async () => {

    const sessionId = sessionStorage.getItem("session_id");

    if (!sessionId) {
        alert("Session not found.");
        window.location.href = "/";
        return;
    }

    try {

        const response = await fetch(`/api/get-session-results/${sessionId}`);

        if (!response.ok) {
            throw new Error("Unable to fetch results");
        }

        const data = await response.json();
        const score = Math.round(data.overall_score);

document.getElementById("overallScoreText").textContent =
    score + "%";

const circle = document.getElementById("scoreBar");

const radius = 75;
const circumference = 2 * Math.PI * radius;

circle.style.strokeDasharray = circumference;

const offset =
    circumference - (score / 100) * circumference;

setTimeout(() => {
    circle.style.strokeDashoffset = offset;
}, 300);

        // Hide loading
        document.getElementById("dashLoading").classList.add("d-none");
        document.getElementById("dashContent").classList.remove("d-none");

        document.getElementById("dashDomain").textContent =
            data.domain;

        document.getElementById("dashTime").textContent =
            "Completed : " + data.created_at;

        document.getElementById("overallScoreText").textContent =
            Math.round(data.overall_score) + "%";

        document.getElementById("scoreBar").style.width =
            Math.round(data.overall_score) + "%";

        document.getElementById("metricTechnical").textContent =
            Math.round(data.metrics.technical) + "%";

        document.getElementById("metricCommunication").textContent =
            Math.round(data.metrics.communication) + "%";

        document.getElementById("metricBehavioral").textContent =
            Math.round(data.metrics.behavioral) + "%";

        document.getElementById("metricStress").textContent =
            Math.round(data.metrics.stress_handling) + "%";

        const recommendationList =
            document.getElementById("recommendationsList");

        recommendationList.innerHTML = "";

        data.recommendations.forEach(item => {

            const li = document.createElement("li");

            li.textContent = item;

            recommendationList.appendChild(li);

        });

        const accordion =
            document.getElementById("questionLogsAccordion");

        accordion.innerHTML = "";

        data.responses.forEach((response, index) => {

            accordion.innerHTML += `

            <div class="accordion-item">

                <h2 class="accordion-header">

                    <button class="accordion-button collapsed"
                        type="button"
                        data-bs-toggle="collapse"
                        data-bs-target="#collapse${index}">

                        Question ${index + 1}

                    </button>

                </h2>

                <div id="collapse${index}"
                     class="accordion-collapse collapse">

                    <div class="accordion-body">

                        <strong>Question :</strong><br>

                        ${response.question_text || ""}

                        <hr>

                        <strong>Your Answer :</strong><br>

                        ${response.candidate_answer || ""}

                    </div>

                </div>

            </div>

            `;

        });

    }

    catch (error) {

        console.error(error);

        alert("Unable to load dashboard results.");

    }

});