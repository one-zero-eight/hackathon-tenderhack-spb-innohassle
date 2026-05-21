import Button from '@/components/ui/Button'
import Checkbox from '@/components/ui/Checkbox'
import Dropdown from '@/components/ui/Dropdown'
import FileInput from '@/components/ui/FileInput'
import Input from '@/components/ui/Input'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import LoggingProgressBar from '@/components/ui/LoggingProgressBar'
import Radio from '@/components/ui/Radio'
import { createFileRoute } from '@tanstack/react-router'
import { useState } from 'react'

export const Route = createFileRoute('/previews')({
  component: RouteComponent,
})

interface Option {
  id: number
  value: string
  label: string
}

const dropdownOptions: Option[] = [
  { id: 0, value: 'option 1', label: 'option 1' },
  { id: 0, value: 'option 2', label: 'option 2' },
]

function RouteComponent() {
  const [, setDropdownChoice] = useState<string>(dropdownOptions[0].value)

  return (
    <div className="flex flex-col gap-8 p-10">
      <Button variant="primary" size="sm">
        Button
      </Button>
      <Button variant="outline" size="sm">
        Button
      </Button>
      <Checkbox label="Checkbox" />
      <Dropdown options={dropdownOptions} onSelect={(v) => setDropdownChoice(v)} />
      <FileInput />
      <Input size="md" placeholder="Input field" />
      <LoadingSpinner />
      <LoggingProgressBar progress={0.4} />
      <fieldset className="flex flex-col gap-2">
        <Radio name="radio" label="choice 1" />
        <Radio name="radio" label="choice 2" />
      </fieldset>
    </div>
  )
}
