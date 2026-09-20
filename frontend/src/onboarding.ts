/**
 * Lives apart from OnboardingPage so App.tsx can read the flag without
 * importing the component (#271). An eager `import { ONBOARDING_FLAG } from
 * './pages/OnboardingPage'` would pull the whole module into the entry chunk
 * and defeat lazily loading that route.
 */
export const ONBOARDING_FLAG = 'fitman_onboarding_pending'
