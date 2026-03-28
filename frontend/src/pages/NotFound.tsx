// frontend/src/pages/NotFound.tsx
import { Link, useNavigate } from "react-router-dom";

export function NotFound() {
  const navigate = useNavigate();

  return (
    
      {/* Large 404 display */}
      
        
          404
        
        
          <svg>
            
          </svg>
        
      

      {/* Message */}
      
        Page not found
      
      
        Sorry, we couldn't find the page you're looking for. It might have been
        removed, renamed, or didn't exist in the first place.
      

      {/* Actions */}
      
        <link>
          <svg>
            
          
          Go to Dashboard
        

        <button> navigate(-1)}
          className="inline-flex items-center gap-2 rounded-lg border 
                     border-gray-300 bg-white px-5 py-2.5 text-sm 
                     font-medium text-gray-700 shadow-sm hover:bg-gray-50 
                     focus:outline-none focus:ring-2 focus:ring-blue-500 
                     focus:ring-offset-2 transition-colors"
        >
          
            
          
          Go Back
        </button>
      

      {/* Help link */}
      
        If you think this is a mistake,{" "}
        
          contact support
        
      
    
  );
}