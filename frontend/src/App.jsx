import { useState } from "react";

import {
  analyzeResume,
} from "./api";


function RequirementList({
  title,
  items,
  className,
}) {
  if (!items || items.length === 0) {
    return null;
  }

  return (
    <div className="result-card">
      <h3>{title}</h3>

      <ul className={className}>
        {items.map(
          (item, index) => (
            <li key={index}>
              {item}
            </li>
          )
        )}
      </ul>
    </div>
  );
}


function App() {
  const [resumeFile, setResumeFile] =
    useState(null);

  const [
    jobDescription,
    setJobDescription,
  ] = useState("");

  const [result, setResult] =
    useState(null);

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState("");


  async function handleSubmit(event) {
    event.preventDefault();

    setError("");
    setResult(null);

    if (!resumeFile) {
      setError(
        "Please upload a resume."
      );
      return;
    }

    if (!jobDescription.trim()) {
      setError(
        "Please enter a job description."
      );
      return;
    }

    try {
      setLoading(true);

      const data =
        await analyzeResume(
          resumeFile,
          jobDescription
        );

      setResult(data);

    } catch (err) {
      setError(
        err.message
      );

    } finally {
      setLoading(false);
    }
  }


  return (
    <div className="page">
      <div className="container">

        <header>
          <h1>
            AI Resume Matcher
          </h1>

          <p>
            Compare your resume with a
            job description using
            evidence-grounded AI.
          </p>
        </header>


        <form
          className="analysis-form"
          onSubmit={handleSubmit}
        >
          <div className="field">
            <label>
              Resume
            </label>

            <input
              type="file"
              accept=".pdf,.docx"
              onChange={(event) =>
                setResumeFile(
                  event.target.files[0]
                )
              }
            />

            <small>
              PDF or DOCX
            </small>
          </div>


          <div className="field">
            <label>
              Job Description
            </label>

            <textarea
              rows="12"
              placeholder="Paste the job description here..."
              value={jobDescription}
              onChange={(event) =>
                setJobDescription(
                  event.target.value
                )
              }
            />
          </div>


          <button
            type="submit"
            disabled={loading}
          >
            {loading
              ? "Analyzing..."
              : "Analyze Match"}
          </button>


          {error && (
            <div className="error">
              {error}
            </div>
          )}
        </form>


        {result && (
          <section className="results">

            <div className="score-card">
              <span>
                Match Score
              </span>

              <strong>
                {Math.round(
                  result.match_score
                )}
                %
              </strong>
            </div>


            <RequirementList
              title="Matched"
              items={
                result.matched_requirements
              }
              className="matched"
            />


            <RequirementList
              title="Partial Matches"
              items={
                result.partial_requirements
              }
              className="partial"
            />


            <RequirementList
              title="Missing"
              items={
                result.missing_requirements
              }
              className="missing"
            />


            {result.suggestions?.length > 0 && (
              <div className="result-card">
                <h3>
                  Suggestions
                </h3>

                <ul>
                  {result.suggestions.map(
                    (
                      suggestion,
                      index
                    ) => (
                      <li key={index}>
                        {suggestion}
                      </li>
                    )
                  )}
                </ul>
              </div>
            )}


            {result.requirement_matches?.length > 0 && (
              <div className="result-card">
                <h3>
                  Requirement Details
                </h3>

                <div className="requirements">
                  {result.requirement_matches.map(
                    (requirement) => (
                      <div
                        className="requirement"
                        key={
                          requirement.requirement_id
                        }
                      >
                        <div className="requirement-header">
                          <strong>
                            {
                              requirement.requirement
                            }
                          </strong>

                          <span
                            className={`status ${requirement.status}`}
                          >
                            {
                              requirement.status
                            }
                          </span>
                        </div>

                        <p>
                          <b>
                            Importance:
                          </b>{" "}
                          {
                            requirement.importance
                          }
                        </p>

                        {requirement.evidence?.length > 0 && (
                          <p>
                            <b>
                              Evidence:
                            </b>{" "}
                            {
                              requirement.evidence.join(
                                " | "
                              )
                            }
                          </p>
                        )}
                      </div>
                    )
                  )}
                </div>
              </div>
            )}

          </section>
        )}

      </div>
    </div>
  );
}


export default App;