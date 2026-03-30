import { Link, useNavigate } from "react-router-dom";

export function NotFound() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8 text-center">
        {/* Large 404 display */}
        <div>
          <h1 className="text-9xl font-bold text-gray-900 tracking-tight">
            404
          </h1>
          <div className="mx-auto h-12 w-12 text-gray-400">
            <svg
              className="h-12 w-12"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9.172 16.172a4 4 0 015.656 0M9 12h6m-3-9h.01m-4.98 4L12 7l4.97-.5"
              />
            </svg>
          </div>
        </div>

        {/* Message */}
        <h2 className="mt-6 text-3xl font-extrabold text-gray-900">
          Page not found
        </h2>
        <p className="mt-2 text-sm text-gray-600">
          Sorry, we couldn't find the page you're looking for. It might have been
          removed, renamed, or didn't exist in the first place.
        </p>

        {/* Actions */}
        <div className="mt-6 flex items-center justify-center gap-4">
          <Link
            to="/"
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 
                       px-5 py-2.5 text-sm font-medium text-white shadow-sm 
                       hover:bg-blue-700 focus:outline-none focus:ring-2 
                       focus:ring-blue-500 focus:ring-offset-2 transition-colors"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
            Go to Dashboard
          </Link>

          <button
            onClick={() => navigate(-1)}
            className="inline-flex items-center gap-2 rounded-lg border 
                       border-gray-300 bg-white px-5 py-2.5 text-sm 
                       font-medium text-gray-700 shadow-sm hover:bg-gray-50 
                       focus:outline-none focus:ring-2 focus:ring-blue-500 
                       focus:ring-offset-2 transition-colors"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Go Back
          </button>
        </div>

        {/* Help link */}
        <p className="mt-6 text-xs text-gray-500">
          If you think this is a mistake,{" "}
          <a href="mailto:support@example.com" className="font-medium text-blue-600 hover:text-blue-500">
            contact support
          </a>
        </p>
      </div>
    </div>
  );
}