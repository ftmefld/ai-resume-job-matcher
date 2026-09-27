const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL;


export async function analyzeResume(
  resumeFile,
  jobDescription
) {
  const formData = new FormData();

  formData.append(
    "resume_file",
    resumeFile
  );

  formData.append(
    "job_description",
    jobDescription
  );

  const response = await fetch(
    `${API_BASE_URL}/analyze-file`,
    {
      method: "POST",
      body: formData,
    }
  );

  const data = await response.json();

  if (!response.ok) {
    throw new Error(
      data.detail ||
      "Analysis failed."
    );
  }

  return data;
}