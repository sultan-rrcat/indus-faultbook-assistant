CREATE TABLE [dbo].[fault_bookv3](
	[fault_id] [bigint] NOT NULL,
	[fault_time] [datetime] NOT NULL,
	[fault_duration] [varchar](25) NOT NULL,
	[system_name] [varchar](50) NULL,
	[device_name] [varchar](50) NULL,
	[fault_description] [varchar](2000) NULL,
	[persons_involved] [varchar](200) NULL,
	[action_taken] [varchar](500) NULL,
	[faulty_system] [varchar](200) NULL,
	[human_error] [varchar](200) NULL,
	[document] [image] NULL,
	[document_name] [varchar](50) NULL,
	[fda_entry] [varchar](3) NOT NULL,
	[logged_by] [varchar](25) NULL,
	[log_time] [datetime] NULL,
	[first_observation] [varchar](4000) NOT NULL,
	[beam_affected] [varchar](3) NOT NULL
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]