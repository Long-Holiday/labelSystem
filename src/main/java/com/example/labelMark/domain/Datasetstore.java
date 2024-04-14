package com.example.labelMark.domain;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import java.io.Serializable;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.Getter;
import lombok.Setter;

/**
 * <p>
 * 
 * </p>
 *
 * @author wh
 * @since 2024-04-12
 */
@Getter
@Setter
@TableName("datasetstore")
@ApiModel(value = "Datasetstore对象", description = "")
public class Datasetstore implements Serializable {

    private static final long serialVersionUID = 1L;

    @TableField("sampleid")
    private Integer sampleid;

    @TableField("samplename")
    private String samplename;

    @TableField("taskid")
    private Integer taskid;

    @ApiModelProperty("1公开，0不公开")
    @TableField("ispublic")
    private Integer ispublic;


}
