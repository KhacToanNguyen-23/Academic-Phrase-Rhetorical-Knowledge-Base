import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

// Radix Select cannot hold an empty-string item, so "no choice" is mapped to a sentinel here.
const ANY = "__any__";

type SelectFieldProps = {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  /** Label of the "no choice" item. Leave out when a value is always required. */
  anyLabel?: string;
  hint?: string;
};

function SelectField({ id, label, value, onChange, options, anyLabel, hint }: SelectFieldProps) {
  return (
    <Field>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      <Select
        value={value === "" && anyLabel ? ANY : value}
        onValueChange={(next) => onChange(next === ANY ? "" : next)}
      >
        <SelectTrigger id={id} className="w-full">
          <SelectValue placeholder="Select…" />
        </SelectTrigger>
        <SelectContent>
          {anyLabel && <SelectItem value={ANY}>{anyLabel}</SelectItem>}
          {options.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {hint && <FieldDescription>{hint}</FieldDescription>}
    </Field>
  );
}

export { SelectField };
