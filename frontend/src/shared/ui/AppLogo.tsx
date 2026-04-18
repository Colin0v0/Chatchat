interface AppLogoProps {
  className?: string;
}

export function AppLogo({ className = "h-5 w-5" }: AppLogoProps) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      viewBox="0 0 1024 1024"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M853.333333 113.777778v341.333333H512v341.333333H398.222222l-170.666666 170.666667v-170.666667H56.888889V113.777778h796.444444z m113.777778 398.222222v398.222222h-398.222222V512h398.222222z m-227.555555 113.777778h-56.888889v113.777778h56.888889v-113.777778z m170.666666 0h-56.888889v113.777778h56.888889v-113.777778z"
        fill="currentColor"
      />
    </svg>
  );
}
