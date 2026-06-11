type Props = {
  title: string;
  steps: string[];
};

export default function InstallCard({ title, steps }: Props) {
  return (
    <div className="install-card">
      <h3>{title}</h3>

      {steps.map((step, index) => (
        <div key={step} className="install-step">
          <span>{index + 1}</span>

          <p>{step}</p>
        </div>
      ))}
    </div>
  );
}
