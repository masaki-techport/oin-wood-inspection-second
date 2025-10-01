/**
 * Utility functions for handling browser navigation in the inspection screen
 */

/**
 * Sets up global event listeners for browser navigation events
 * This should be called from the main application level to ensure browser navigation
 * buttons trigger our custom handlers when the inspection page is active.
 */
export const setupBrowserNavigationHandlers = () => {
  // Function to determine if we're on the inspection screen
  const isInspectionScreen = () => {
    return window.location.pathname.includes('/inspection');
  };

  // Add a history entry first to ensure we can catch the popstate
  // when the user presses the back button
  const setupHistoryForBackDetection = () => {
    if (isInspectionScreen()) {
      // Push a history entry with the same URL to create a history stack
      window.history.pushState({ inspectionScreen: true }, document.title, window.location.href);
    }
  };

  // Override the back button behavior
  const handleBackButton = (event: PopStateEvent) => {
    if (isInspectionScreen() && (window as any).handleInspectionBackButton) {
      // Prevent default doesn't work with popstate, so we push state again
      // to stay on the current page
      window.history.pushState({ inspectionScreen: true }, document.title, window.location.href);
      // Call our custom handler
      (window as any).handleInspectionBackButton();
    }
  };

  // Note: beforeunload event is now handled by the useBrowserNavigation hook
  // to prevent conflicts and ensure custom dialog behavior

  // Initialize history and add event listeners
  setupHistoryForBackDetection();
  window.addEventListener('popstate', handleBackButton);

  // Return a cleanup function
  return () => {
    window.removeEventListener('popstate', handleBackButton);
  };
};

/**
 * Returns an object with handlers for each navigation action
 */
export const getBrowserNavigationHandlers = () => {
  return {
    handleBackButton: () => {
      if ((window as any).handleInspectionBackButton) {
        (window as any).handleInspectionBackButton();
      }
    },
    handleCloseButton: () => {
      if ((window as any).handleInspectionCloseButton) {
        (window as any).handleInspectionCloseButton();
      }
    },
    handleRefreshButton: () => {
      if ((window as any).handleInspectionRefreshButton) {
        (window as any).handleInspectionRefreshButton();
      }
    }
  };
};

export default setupBrowserNavigationHandlers;
